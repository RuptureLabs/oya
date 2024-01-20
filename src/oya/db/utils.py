from typing import Type

class CustomListener(dict):
    # By https://github.com/antixar
    # At https://github.com/tortoise/tortoise-orm/issues/1071

    def get(self, cls: Type, default=None):
        """Tries to look for signals with MRO logic
        """
        listeners = super().get(cls, default)
        if not listeners:
            for parent_cls in cls.__bases__:
                listeners = self.get(parent_cls, default=default)
                if listeners:
                    return listeners
        else:
            return listeners
        return []


