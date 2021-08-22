# parallel-pyspin #
This package provides another layer of abstraction on top of the Python wrapper for FLIR's [Spinnaker Software Development Kit](https://www.flir.com/products/spinnaker-sdk/) (SDK). This new layer of abstraction provides these additional features:

1. parallel operation of cameras via the [multiprocessing](https://docs.python.org/2/library/multiprocessing.html) package
2. encapsulation of the procedure for configuring multiple cameras for synchronous video acquisition

For documentation of the installation procedure and basic usage please refer to the repository's [wiki](https://github.com/jbhunt/parallel-pyspin/wiki). For questions or general correspondence please send an email to hunt.brian.joshua@gmail.com.

# Basic usage #
## Creating an instance of a primary camera ##
```Python
from llpyspin import primary
cam1 = primary.PrimaryCamera(str(<serial number>))
cam1.prime('<file path>.mp4', backend='Spinnaker') # Available backends for video writing include OpenCV, Spinnaker, and FFmpeg
cam1.trigger()
timestamps = cam1.stop() # the stop method returns the timestamps for each frame (in milliseconds)
cam1.release() # make sure to release the camera when you are done
```

## Adding one or more secondary cameras ##
```Python
from llpysin import secondary
cam2 = secondary.SecondaryCamera(str(<serial number>))
cam2.prime('<file path>.mp4', cam1.framerate) # The prime method requires the framerate of the primary camera as an argument
cam1.prime('<file path>.mp4')
cam1.trigger() # Triggering the primary camera will trigger the secondary camera
timestamps1 = cam1.stop() # Always stop the primary camera before the secondary camera
timestamps2 = cam2.stop()
```
