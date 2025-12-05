# Set environment variables to suppress GTK warnings in headless mode
# This must be done before any Gramps imports
import os

os.environ.setdefault("GDK_BACKEND", "x11")
os.environ.setdefault("NO_AT_BRIDGE", "1")
os.environ.setdefault("GTK_USE_PORTAL", "0")
