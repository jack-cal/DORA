class ValidationError(ValueError):
    """A tested rule is violated; the state transition must not be committed."""


class InvalidTransaction(ValidationError):
    pass


class MempoolFull(ValidationError):
    """Temporary local capacity refusal; the transaction was not queued."""


class InvalidBlock(ValidationError):
    """A full block violates a rule fixed by its known parent and contents."""


class TransientValidationError(ValidationError):
    """A block can be retried after local conditions such as time change."""


class UnsupportedFeature(RuntimeError):
    """Development profile lacks a feature; do not cache as consensus-invalid."""


class StorageError(RuntimeError):
    pass


class MiningExhausted(RuntimeError):
    """One header's nonce space is exhausted; a miner may build a new template."""
