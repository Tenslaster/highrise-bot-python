"""Run bots with the standard `highrise module:Bot ROOM TOKEN` command."""

from highrise_fast import (
    KEEPALIVE_RATE as KEEPALIVE_RATE,
)
from highrise_fast import (
    READ_TIMEOUT as READ_TIMEOUT,
)
from highrise_fast import (
    SDK_NAME as SDK_NAME,
)
from highrise_fast import (
    VERSION as VERSION,
)
from highrise_fast import (
    BotDefinition as BotDefinition,
)
from highrise_fast import (
    bot_runner as bot_runner,
)
from highrise_fast import (
    control_runner as control_runner,
)
from highrise_fast import (
    gather_subscriptions as gather_subscriptions,
)
from highrise_fast import (
    main as run,
)
from highrise_fast import (
    main_async,
)
from highrise_fast import (
    throttler as throttler,
)

main = main_async

if __name__ == "__main__":
    run()
