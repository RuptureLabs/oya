# pylint: disable=E1101,W0212

import sys
from typing import Any, List, Optional, Dict
from tortoise import (
        fields, models, transactions, queryset)
from tortoise.signals import pre_delete, post_save, Signals
from tortoise.backends.base.client import BaseDBAsyncClient
from tortoise.indexes import Index
from oya.db.utils import CustomListener


def _get_app_model_link(cls : models.Model) -> str:
    """
    Get the app label for the model
    """
    return '.'.join(cls.__module__.split('.')[:-1] + [cls.__name__])


def _closure_model_unicode(self) -> str:
    """
    __unicode implementation for the dynamically created
    <Model>Closure model
    """
    return "Closure model from %s to %s" % (self.parent, self.child)


def create_closure_model(cls : models.Model) -> models.Model:
    """
    Creates a <Model> in the same module as the model
    """
    meta_vals = {
        "unique_together": (("parent", "child"),),
        "indexes" : [
            Index(fields=('parent_id', 'depth', 'child_id')),
            Index(fields=('child_id', 'depth', 'parent_id')),
        ]
    }

    if getattr(cls._meta, "table", None):
        meta_vals["table"] = cls._meta.table + "_closure"

    if getattr(cls._meta, 'schema', None):
        meta_vals['schema'] = cls._meta.schema
        
    
    model = type("%sClosure" % cls.__name__, (models.Model,), {
        'parent' : fields.ForeignKeyField(
            _get_app_model_link(cls),
            related_name=cls.closure_parentref(),
            on_delete=fields.CASCADE,
        ),
        'child' : fields.ForeignKeyField(
            _get_app_model_link(cls),
            related_name=cls.closure_childref(),
            on_delete=fields.CASCADE,
        ),
        'depth' : fields.IntField(default=0),
        '__str__': _closure_model_unicode,
        '__module__' : cls.__module__,
        '__unicode__': _closure_model_unicode,
        'Meta' : type('Meta', (object,), meta_vals)
    })

    setattr(cls, '_closure_model', model)
    return model


class ClosureModelMeta(models.ModelMeta):
    """
    Metaclass for Models inheriting from ClosureModel
    to ensure the Model closure model is created
    """
    def __init__(cls, name, bases, dct):
        """
        Create the closure model
        """
        super(ClosureModelMeta, cls).__init__(name, bases, dct)
        if not cls._meta.abstract:
            setattr(
                sys.modules[cls.__module__],
                "%sClosure" % cls.__name__,
                create_closure_model(cls),
            )



class ClosureModel(models.Model, metaclass=ClosureModelMeta):
    """
    Provides methods to assist in a tree based structure
    """

    ## Set listeners for subclasses
    _listeners: Dict[Signals, CustomListener] = {  # type: ignore
        Signals.pre_save: CustomListener(),
        Signals.post_save: CustomListener(),
        Signals.pre_delete: CustomListener(),
        Signals.post_delete: CustomListener(),
    }

    class Meta:
        abstract = True

    def __setattr__(self, name: str, value: Any) -> None:
        if name.endswith("_id"):
            id_field_name = name
        else:
            id_field_name = "%s_id" % name

        if (
            name.startswith(self._closure_sentinel_attr) and
            hasattr(self, id_field_name) and not self._closure_change_check()
        ):
            if name.endswith('_d'):
                obj_id = value
            elif value:
                if hasattr(value, 'pk'):
                    obj_id = value.pk
                else:
                    obj_id = value
            else:
                obj_id = None

            if getattr(self, id_field_name) != obj_id:
                self._closure_change_init()

        super(ClosureModel, self).__setattr__(name, value)


    @classmethod
    @transactions.atomic
    async def rebuiltable(cls):
        """Regenerate the entire table"""
        await cls._closure_model.all().delete()
        all_pks = await cls.all().values('pk')
        await cls._closure_model.bulk_create([
            cls._closure_model(
                parent_id=x['pk'],
                child_id=x['pk'],
                depth=0
            ) for x in all_pks])
        
        all_nodes = await cls.all()
        for node in all_nodes:
            await node._closure_createlink()

    
    @classmethod
    def closure_parentref(cls):
        """How to refer to parents in the closure tree"""
        return "%sclosure_children" % cls.__name__.lower()
    
    # Backwords compatibility
    _closure_parentref = closure_parentref

    @classmethod
    def closure_childref(cls):
        """How to refer to children in the closure tree"""
        return "%sclosure_parents" % cls.__name__.lower()
    
    # Backwords compatibility
    _closure_childref = closure_childref

    @property
    def _closure_sentinel_attr(self):
        """
        The atrribute we need to watch to tell if te parent/child relations have changed
        """
        meta = getattr(self, "ClosureMeta", None)
        return getattr(meta, 'sentinel_attr', self._closure_parent_attr)
    

    @property
    def _closure_parent_attr(self):
        """
        The attribute we need to watch to tell if the
        parent/child relations have changed
        """
        meta = getattr(self, 'ClosureMeta', None)
        return getattr(meta, 'parent_attr', 'parent')
    

    @property
    def _closure_parent_pk(self):
        """What our parent pk is in the closure tree"""
        if hasattr(self, "%s_id" % self._closure_parent_attr):
            return getattr(self, "%s_id" % self._closure_parent_attr)
        else:
            parent = getattr(self, self._closure_parent_attr)
            return parent.pk if parent else None
        

    async def _closure_deletelink(self, oldparentpk):
        """Remove incorrect links from the closure tree"""
        try:
            filt = await self._closure_model.filter(
                **{
                    "parent__%s__parent_id" % self._closure_childref() : oldparentpk,
                    "child__%s__child_id" % self._closure_parentref() : self.pk
                }
            )
            filt.delete()
        except Exception as e:
            print(e, '------')



    async def _closure_createlink(self):
        """Create a link in the closure tree"""
        linkparents = await self._closure_model.filter(
            child__pk = self._closure_parent_pk
        ).values("parent_id", "depth")

        linkchildren = await self._closure_model.all().filter(
            parent__pk = self.pk
        )

        newlinks = [self._closure_model(
            parent_id=p['parent_id'],
            child_id=c.child_id,
            depth=p['depth'] + c.depth + 1
        ) for p in linkparents for c in linkchildren]
        await self._closure_model.bulk_create(newlinks)


    def get_descendants(self, include_self: bool = False, depth : int = None):
        """Get all descendants of this node"""
        params = {"%s__parent" % self._closure_childref() : self.pk}
        if depth is not None:
            params["%s__depth_lte" % self._closure_childref()] = depth
        descendants = self.filter(**params)
        if not include_self:
            descendants = descendants.exclude(pk=self.pk)
        return descendants.order_by("%s__depth" % self._closure_childref())

    def get_ancestors(self, include_self: bool = False, depth : int = None):
        """Get all ancestors of this node"""
        if self.is_root_node():
            if not include_self:
                return self.filter(pk=self.pk).exclude(pk=self.pk)
            else:
                return self.filter(pk=self.pk)
            
        params = {"%s__child" % self._closure_parentref() : self.pk}
        if depth is not None:
            params["%s__depth_lte" % self._closure_parentref()] = depth
        ancestors = self.filter(**params)
        if not include_self:
            ancestors = ancestors.exclude(pk=self.pk)
        return ancestors.order_by("%s__depth" % self._closure_parentref())

    def prepopulate(self, queryset : queryset.QuerySet):
        """Prepopulate a descendants query's children efficiently.
            Call like : blah.prepopulate(Thing.objects.all())"""
        objs = list(queryset)
        hashobjs = dict([(x.pk, x) for x in objs] + [self.pk, self])
        for descendant in hashobjs.values():
            descendant._cached_children = []

        for descendant in objs:
            assert descendant._closure_parent_pk in hashobjs
            parent = hashobjs[descendant._closure_parent_pk]
            parent._cached_children.append(descendant)


    async def get_children(self):
        """Get all children of this node"""
        if hasattr(self, "_cached_children"):
            children = await self.filter(pk__in=[x.pk for x in self._cached_children])
            children.__result_cache = self._cached_children
            return children
        else:
            return await self.get_descendants(include_self=False, depth=1)


    async def get_root(self):
        """Get the root of this node"""
        if self.is_root_node():
            return self
        
        return await self.get_ancestors().order_by(
            "-%s__depth" % self._closure_parentref()
        ).first()
    
    def is_root_node(self):
        """Is this node a root, i.e. has no parent?"""
        return self._closure_parent_pk is None
    

    async def is_decendant_of(self, other, include_self=False):
        """Is this node a decendant of other?"""
        if other.pk == self.pk:
            return  include_self
        
        return await self._closure_model.filter(
            parent=other,
            child=self
        ).exists()
    

    async def is_ancestor_of(self, other, include_self=False):
        """Is this node an ancestor of other?"""
        return await other.is_decendant_of(self, include_self=include_self)
    
    def _closure_change_init(self):
        """Part of the change detection. Setting up"""
        # More magic. We're setting this inside setattr...
        self._closure_old_parent_pk = self._closure_parent_pk

    def _closure_change_check(self):
        """Part of the change detection. Have we changed since we began?"""
        return hasattr(self,"_closure_old_parent_pk")
    
    def _closure_change_oldparent(self):
        """Part of the change detection. What we used to be"""
        return self._closure_old_parent_pk
    

@post_save(ClosureModel)
async def closure_model_save(
    sender : ClosureModel,
    instance : ClosureModel,
    created : bool,
    using_db : Optional[BaseDBAsyncClient],
    update_fields : List[str]
    ):
    async with transactions.in_transaction():
        if issubclass(sender, ClosureModel):
            if created:
                closure_instance = instance._closure_model(
                    parent=instance,
                    child=instance,
                    depth=0
                )
                await closure_instance.save()
            if instance._closure_change_check():
                #Changed parents.
                if instance._closure_change_oldparent():
                    await instance._closure_deletelink(instance._closure_change_oldparent())
                await instance._closure_createlink()
                delattr(instance, "_closure_old_parent_pk")
            elif created:
                # We still need to create links when we're first made
                await instance._closure_createlink()


@pre_delete(ClosureModel)
async def closure_model_delete(
    sender : ClosureModel,
    instance : ClosureModel,
    using_db : Optional[BaseDBAsyncClient]
    ):
    async with transactions.in_transaction():
        if issubclass(sender, ClosureModel):
            await instance._closure_deletelink(instance._closure_parent_pk)
