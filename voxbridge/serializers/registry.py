"""Serializer registry for VoxBridge.

Provides a central lookup for all available serializers by name.
Custom serializers can be registered at runtime.
"""

from __future__ import annotations

from typing import Type

from loguru import logger

from voxbridge.serializers.base import BaseSerializer


class SerializerRegistry:
    """Registry mapping provider names to serializer classes.

    All built-in serializers are registered automatically on first access.
    Custom serializers can be added via :meth:`register`.

    Usage:
        registry = SerializerRegistry()
        serializer = registry.create("twilio")
        # or
        serializer_cls = registry.get("genesys")
    """

    def __init__(self) -> None:
        self._registry: dict[str, Type[BaseSerializer]] = {}
        self._loaded = False

    def _load_builtins(self) -> None:
        """Lazily load all built-in serializers."""
        if self._loaded:
            return

        from voxbridge.serializers.twilio import TwilioSerializer
        from voxbridge.serializers.genesys import GenesysSerializer
        from voxbridge.serializers.generic_ws import GenericWebSocketSerializer
        from voxbridge.serializers.freeswitch import FreeSwitchSerializer
        from voxbridge.serializers.asterisk import AsteriskSerializer
        from voxbridge.serializers.amazon_connect import AmazonConnectSerializer
        from voxbridge.serializers.avaya import AvayaSerializer
        from voxbridge.serializers.cisco import CiscoSerializer

        builtins: list[tuple[str, Type[BaseSerializer]]] = [
            ("twilio", TwilioSerializer),
            ("genesys", GenesysSerializer),
            ("generic", GenericWebSocketSerializer),
            ("freeswitch", FreeSwitchSerializer),
            ("asterisk", AsteriskSerializer),
            ("amazon_connect", AmazonConnectSerializer),
            ("avaya", AvayaSerializer),
            ("cisco", CiscoSerializer),
        ]

        for name, cls in builtins:
            self._registry[name] = cls

        self._loaded = True
        logger.debug(f"Loaded {len(builtins)} built-in serializers")

    def register(self, name: str, cls: Type[BaseSerializer]) -> None:
        """Register a custom serializer class.

        Args:
            name: The lookup name (e.g., "my_provider").
            cls: The serializer class (must be a subclass of BaseSerializer).
        """
        if not issubclass(cls, BaseSerializer):
            raise TypeError(f"{cls} is not a subclass of BaseSerializer")
        self._registry[name] = cls
        logger.debug(f"Registered custom serializer: {name}")

    def get(self, name: str) -> Type[BaseSerializer]:
        """Get a serializer class by provider name.

        Args:
            name: The provider name (e.g., "twilio", "genesys").

        Returns:
            The serializer class.

        Raises:
            KeyError: If no serializer is registered for the given name.
        """
        self._load_builtins()
        if name not in self._registry:
            available = ", ".join(sorted(self._registry.keys()))
            raise KeyError(
                f"No serializer registered for '{name}'. "
                f"Available: {available}"
            )
        return self._registry[name]

    def create(self, name: str, **kwargs) -> BaseSerializer:
        """Create a serializer instance by provider name.

        Args:
            name: The provider name.
            **kwargs: Arguments passed to the serializer constructor.

        Returns:
            A new serializer instance.
        """
        cls = self.get(name)
        return cls(**kwargs)

    @property
    def available(self) -> list[str]:
        """List all available provider names."""
        self._load_builtins()
        return sorted(self._registry.keys())


# Global singleton
serializer_registry = SerializerRegistry()
