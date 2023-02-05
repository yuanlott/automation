# Paackages where parser modules exist must have following lines in __init__.py
# otherwise the parser through runtime exception during use
from genie import abstract

abstract.declare_package(__name__)
abstract.declare_token(__name__)
