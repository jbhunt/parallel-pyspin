import dill
import PySpin
import numpy as np
import multiprocessing as mp

# relative imports
from .processes  import MainProcess, ChildProcess, CameraError, queued

#
class StreamingChildProcess(ChildProcess):
    """
    """

    def __init__(self, device):
        """
        """

        # create a shared memory list for buffering a single image
        self.buffer = mp.Manager().list()

        #
        super().__init__(device)

        return

class VideoStream(MainProcess):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        self.open()

        return

    def open(self):
        """
        """

        # spawn a child process as needed
        if self._child is None:
            self._spawn_child_process(StreamingChildProcess)
        else:
            raise CameraError('Video stream is already open')

        # set the acquisition flag
        self._child.acquiring.value = 1

        #
        def f(child, camera, **kwargs):

            try:
                camera.BeginAcquisition()

                # main acquisition loop
                while child.acquiring.value:

                    try:
                        image = camera.GetNextImage(kwargs['timeout'])

                        #
                        if not image.IsIncomplete():

                            # convert the image
                            data = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray().flatten()

                            # store the image (critical - use lock)
                            with child.buffer.get_lock():
                                child.buffer[:] = data

                    except PySpin.SpinnakerException:
                        continue

                return True, None

            except PySpin.SpinnakerException:
               return False, None

        # pack the kwargs
        kwargs = {
            'shape'   : (self.width, self.height),
            'timeout' : 1
        }
        self._child.iq.put(dill.dumps(f), kwargs)
        self._locked = True

        return

    def close(self):
        """
        """

        # return if there is no active child or the stream is already closed
        if self._child is None:
            raise CameraError('Video stream is already closed')

        # unset the acquisition flag
        self._child.acquiring.value = 0

        # check the result of video acquisition
        result, output = self._child.oq.get()
        if not result:
            pass

        @queued
        def f(obj, camera, *args, **kwargs):
            try:
                camera.EndAcquisition()
                return True, None
            except:
                return False, None

        # check the result
        result, output = f(self, 'Failed to stop video acquisition')

        # release the acquisition lock
        self._locked = False

        # join the child process
        self._join_child_process()

        return

    def read(self):
        """
        """

        # return if there is no active child or the stream is closed
        if self._child is None:
            raise CameraError('Video stream is closed')

        # grab the image most recently buffered image
        try:
            with self._child.buffer.get_lock():
                data = self._child.buffer[:]
            image = np.array(data, dtype=np.uint8).reshape([self.height, self.width])
            return (True, image)

        except:
            return (False, None)
