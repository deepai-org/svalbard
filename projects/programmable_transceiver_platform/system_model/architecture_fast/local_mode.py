"""Management-only routing profile of the common mathematical chip."""
from chip import TransceiverChip
from management_only_lifecycle import ManagementChip

class LocalTransceiverChip(ManagementChip,TransceiverChip):
    """Disable streaming pins/watchdog; route RF capture into local memory."""
    pass
