#!/bin/bash
# Disabled: session documents require an explicit user request.
# Consume input safely if an open session still has this command cached.
/bin/cat > /dev/null
exit 0
