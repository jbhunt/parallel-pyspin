
# coded values

# outcomes
ABORTED    = -1
FAILURE    =  0
SUCCESS    =  1

# commands
INITIALIZE =  2
SET        =  3
START      =  4
STOP       =  5
RELEASE    =  6

# acquisition properties

# framerate
FRAMERATE_ID            = 7
FRAMERATE_MAXIMUM_VALUE = 120
FRAMERATE_MINIMUM_VALUE = 1
FRAMERATE_DEFAULT_VALUE = 30

# exposure
EXPOSURE_ID           = 8
EXPOSURE_MAXIMUM_VALUE = 10000
EXPOSURE_MINIMUM_VALUE = 100
EXPOSURE_DEFAULT_VALUE = 1500

# binize
BINSIZE_ID               = 9
BINSIZE_PERMITTED_VALUES = [1,2,4]
BINSIZE_DEFAULT_VALUE    = 1

# stream buffer handling mode
BUFFER_MODE_ID               = 10
BUFFER_MODE_PERMITTED_VALUES = ['NewestOnly','NewestFirst','OldestFirst']
BUFFER_MODE_DEFAULT_VALUE    = 'NewestOnly'

# acquisition mode
ACQUISITION_MODE_ID               = 11
ACQUISITION_MODE_PERMITTED_VALUES = ['Continuous']
ACQUISITION_MODE_DEFAULT_VALUE    = 'Continuous'

# pixel format
PIXEL_FORMAT_ID               = 12
PIXEL_FORMAT_PERMITTED_VALUES = ['Mono8']
PIXEL_FORMAT_DEFAULT_VALUE    = 'Mono8'
