# imports
import os
import yaml

# this is the relative path to the package
PACKAGE_PATH = os.path.dirname(__file__)
CONFIG_FILE  = os.path.join(PACKAGE_PATH,'config.yaml')
with open(CONFIG_FILE) as stream:
    CONFIG_DATA = yaml.full_load(stream)

# primary and secondary camera serial numbers and nicknames
PRIMARY_SERIALNO    = str(CONFIG_DATA['cameras']['primary']['serialno'])
PRIMARY_NICKNAME    = str(CONFIG_DATA['cameras']['primary']['nickname'])
SECONDARY_SERIALNOS = list(map(str,CONFIG_DATA['cameras']['secondary']['serialno']))
SECONDARY_NICKNAMES = list(map(str,CONFIG_DATA['cameras']['secondary']['nickname']))

# image size and shape
IMAGE_WIDTH  = CONFIG_DATA['cameras']['primary']['resolution'][0]
IMAGE_HEIGHT = CONFIG_DATA['cameras']['primary']['resolution'][1]
IMAGE_SIZE   = IMAGE_WIDTH * IMAGE_HEIGHT
IMAGE_SHAPE  = (IMAGE_HEIGHT,IMAGE_WIDTH) # convenient for shaping numpy arrays

# basic capture properties
CAP_PROP_FPS      = 'framerate'
CAP_PROP_BINSIZE  = 'binsize'
CAP_PROP_EXPOSURE = 'exposure'
CAP_PROP_WIDTH    = 'width'
CAP_PROP_HEIGHT   = 'height'
CAP_PROP_OFFSET   = 'offset'

# default values for the basic capture properties
CAP_PROP_FPS_DEFAULT      = 60
CAP_PROP_BINSIZE_DEFAULT  = 2
CAP_PROP_EXPOSURE_DEFAULT = 1500
CAP_PROP_WIDTH_DEFAULT    = IMAGE_WIDTH
CAP_PROP_HEIGHT_DEFAULT   = IMAGE_HEIGHT
CAP_PROP_OFFSET_DEFAULT   = (0,0)

# buffer handling mode property and valid modes
CAP_PROP_BUFFER_HANDLING_MODE           = 'buffermode'
CAP_PROP_BUFFER_HANDLING_MODE_DEFAULT   = 'MostRecentFirst'
CAP_PROP_BUFFER_HANDLING_MODE_STREAMING = 'NewestOnly'
CAP_PROP_BUFFER_HANDLING_MODE_RECORDING = 'MostRecentFirst'

#
SUPPORTED_CAP_PROPS = (
    CAP_PROP_FPS,
    CAP_PROP_BINSIZE,
    CAP_PROP_EXPOSURE,
    CAP_PROP_BUFFER_HANDLING_MODE
    )
