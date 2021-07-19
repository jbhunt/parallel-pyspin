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

        #
        super().__init__(device)

        # This queue acts as a buffer holding a single image
        self.buffer = mp.Queue()

        # This lock prevents reading and writing to the buffer at the same time
        self.qlock = mp.Lock()

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

                            # store the image (critical - use lock)
                            with child.qlock:

                                # remove the previous image
                                if child.buffer.qsize() > 0:
                                    previous = child.buffer.get()

                                # replace with the current image
                                child.buffer.put(image.GetNDArray())

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
        item = (dill.dumps(f), kwargs)
        self._child.iq.put(item)
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
        def f(child, camera):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                if camera.IsInitialized():
                    camera.DeInit()
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
            with self._child.qlock:
                image = self._child.buffer.get()
            return (True, image)

        except:
            return (False, None)
