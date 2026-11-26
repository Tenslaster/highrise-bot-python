"""Models and converter for Highrise instance control connections."""

from cattrs.preconf.json import make_converter
from highrise_fast import (
    ControlSessionMetadata as ControlSessionMetadata,
)
from highrise_fast import (
    InstanceStartedEvent as InstanceStartedEvent,
)
from highrise_fast import (
    InstanceStoppedEvent as InstanceStoppedEvent,
)
from highrise_fast import (
    KeepaliveResponse,
)

from ._unions import configure_tagged_union

ControlEvent = InstanceStartedEvent | InstanceStoppedEvent | KeepaliveResponse
converter = make_converter()
configure_tagged_union(ControlEvent, converter)
