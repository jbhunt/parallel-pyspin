import PySpin
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from .processes  import MainProcess, ChildProcess
from . import recording

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class SecondaryCameraV2(MainProcess):
    """
    """

    def __init__(self, device):
        """
        """

        super().__init__(device)

        # start the child process
        self._initialize()

        # unset these property values (they are determined by the primary camera)
        self._framerate = None
        self._exposure  = None

        # set the buffer handling mode to oldest first (instead of newest only)
        def f(obj, camera, *args, **kwargs):
            try:
                camera.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)
                return True
            except PySpin.SpinnakerException:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to set the buffer handling mode')

        #
        self._primed = False

        return

    def prime(self, filename, backend='ffmpeg'):
        """
        """

        if self.primed:
            logging.log(logging.WARNING, f'camera[{self._device}] is already primed')

        if backend not in ['ffmpeg', 'PySpin']:
            raise ValueError(f'{backend} is not a valid backend for writing video')

        def f(obj, camera, *args, **kwargs):

            try:

                # initialize the video writer
                if kwargs['backend'] == 'ffmpeg':
                    writer = recording.VideoWriterFFmpeg().open(kwargs['filename'], kwargs['shape'], kwargs['framerate'])
                elif kwargs['backend'] == 'PySpin':
                    writer = recording.VideoWriterPySpin().open(kwargs['filename'], kwargs['framerate'], kwargs['bitrate'])
                else:
                    return False

                # configure the hardware trigger
                camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
                camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
                camera.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                # begin acquisition
                camera.BeginAcquisition()

                # main loop
                while obj.acquiring.value:

                    # There's a 1 ms timeout for the call to GetNextImage to prevent
                    # the secondary camera from blocking when video acquisition is
                    # aborted before the primary camera is triggered (see below).

                    try:
                        result = camera.GetNextImage(1) # timeout
                    except PySpin.SpinnakerException:
                        continue

                    #
                    if not image.IsIncomplete():
                        writer.write(result)

                #
                writer.close()

                return True

            except PySpin.SpinnakerException:
                return False

        kwargs = {
            'filename'  : filename,
            'shape'     : (self.height, self.width),
            'framerate' : 30,
            'bitrate'   : 1000000,
            'backend'   : 'ffmpeg'
        }
        item = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)

        self._primed = True

        return

    def stop(self):
        """
        """

        if not self._primed:
            logging.log(logging.INFO, f'camera[{self._device}] is not primed')
            return

        # query the result of video acquisition
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'video acquisition for camera[{self._device}] failed')

        def f(obj, camera, *args, **kwargs):
            try:
                camera.EndAcquisition()
                camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)
                return True
            except:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'video deacquisition for camera[{self._device}] failed')

        self._primed = False

        return

    def close(self):
        """
        """

        self._release()

        return

    @property
    def primed(self):
        return self._primed
