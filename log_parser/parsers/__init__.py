"""Parser plugin package.

This subpackage contains discrete parser implementations for
recognizing specific log formats. Each module should define a
class with ``match`` and ``parse`` methods. Instances of these
classes will be created automatically when the parsing engine
initializes. See :mod:`log_parser.parser_engine` for details.

Included parsers:

* :class:`JSONParser` – parse structured JSON log lines.
* :class:`NginxApacheParser` – parse Nginx/Apache combined log format.
* :class:`CustomParser` – parse `[LEVEL] YYYY-MM-DD HH:MM:SS ...` logs.
* :class:`MinecraftParser` – parse Minecraft `latest.log` format.

You can add your own parser by creating a new module in this
subpackage and defining a class that has ``match`` and ``parse`` methods.
"""