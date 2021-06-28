import dill
import PySpin
import numpy as np
import multiprocessing as mp

# relative imports
from .processes  import MainProcess, ChildProcess, CameraError, queued
from .recording  import VideoWriterFFmpeg, VideoWriterSpinnaker

class SecondaryCamera(MainProcess):
    """
    """

    def __init__(self, device: int=1):
        """
        """

        super().__init__(device)

        return

    def prime(self, filename, timestamp=True, bitrate=1000000, backend='ffmpeg'):
        """
        """

        # spawn a new child process if necessary
        if self._child is None:
            self._spawn_child_process(ChildProcess)

        # set the buffer handling mode to oldest first (instead of newest only)
        @queued
        def f(obj, camera, **kwargs):
            try:
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_OldestFirst)
                return True, None
            except PySpin.SpinnakerException:
                return False, None

        # call the function
        result, output = f(self, 'Failed to set buffer handling mode')

        # begin acquisition
        # NOTE - This is a special case in which the queued decorator won't
        #        work because trying to retrieve the result from the child's
        #        output queue will cause the main process to hang.
        def f(obj, camera, **kwargs):

            try:

                # begin acquisition
                camera.BeginAcquisition()

                # initialize the video writer
                if kwargs['backend'] == 'ffmpeg':
                    writer = VideoWriterFFmpeg()
                elif kwargs['backend'] == 'spinnaker':
                    writer = VideoWriterSpinnaker()
                else:
                    return False, None
                writer.open(kwargs['filename'], kwargs['shape'], kwargs['framerate'], kwargs['bitrate'])

                # create the timestamps file
                if kwargs['timestamp']:
                    # TODO - implement a timestamping procedure
                    pass

                # configure the hardware trigger for a secondary camera
                camera.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
                camera.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
                camera.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
                camera.TriggerMode.SetValue(PySpin.TriggerMode_On)

                # begin acquisition
                camera.BeginAcquisition()

                return True, None

            except PySpin.SpinnakerException:
                return False, None

        # kwargs for configuring up the video writing
        kwargs = {
            'filename'  : filename,
            'timestamp' : timestamp,
            'shape'     : (self.height, self.width),
            'framerate' : self.framerate,
            'bitrate'   : bitrate,
            'backend'   : backend,
        }

        # place the function in the input queue
        item = (dill.dumps(f), kwargs)
        self._child.iq.put(item)

        #
        self._primed = True
        self._locked = True

        return

    def start(self, timeout=1):
        """
        """

        if not self.primed:
            raise CameraError('Camera is not primed')

        def f(child, camera, **kwargs)

            # main loop
            while obj.acquiring.value:

                # There's a 1 ms timeout for the call to GetNextImage to prevent
                # the secondary camera from blocking when video acquisition is
                # aborted before the primary camera is triggered (see below).

                try:
                    pointer = camera.GetNextImage(kwargs['timeout']) # timeout
                except PySpin.SpinnakerException:
                    continue

                #
                if not pointer.IsIncomplete():
                    writer.write(pointer)

                pointer.Release()

            # reset the trigger mode
            camera.TriggerMode.SetValue(PySpin.TriggerMode_Off)

            #
            writer.close()

            return True, None

        except PySpin.SpinnakerException:
            return False, None

        # NOTE - The acquisition flag needs to be set before placing the
        #        acquisition function in the child's input queue
        self.acquiring.value = 1

        # place the acquisition function in the child's input queue
        item = (dill.dumps(f), {'timeout': timeout})
        self._child.iq.put(item)

        return

    def stop(self):
        """
        """

        if self._child.acquiring.value != 1:
            raise CameraError('Camera is not acquiring')

        # stop acquisition
        self._child.acquiring.value = 0

        # query the result of video acquisition
        result, output = self._child.oq.get()

        @queued
        def f(obj, camera, **kwargs):
            try:
                camera.EndAcquisition()
                camera.DeInit()
                return True, None
            except:
                return False, None

        result, output = f(self, 'Failed to stop video acquisition')

        self._join_child_process()

        self._primed = False
        self._locked = False

        return

    @property
    def primed(self):
        return self._primed
