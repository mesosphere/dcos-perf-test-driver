from .SingleLineCodec import SingleLineCodec
from .MultilineCodec import MultilineCodec

# Lookup of codec class by name
CodecTypes = {"singleline": SingleLineCodec, "multiline": MultilineCodec}
