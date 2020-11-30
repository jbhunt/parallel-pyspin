import dill
import queue
import PySpin
import logging
import numpy as np
import multiprocessing as mp

# relative imports
from ._processes  import MainProcess, ChildProcess, ChildProcessError

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

#
class ChildProcessStreaming(ChildProcess):
    """
    """

    def __init__(self, device):
        """
        """

        # create a shared memory array for storing a single image
        self.buffer = self._createBuffer(device)

        #
        super().__init__(device)

        return

    def _createBuffer(self, device):
        """
        this method determines the size of the image buffer on instantiation
        """

        #
        try:
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()
            camera  = cameras.GetByIndex(device)
            camera.Init()
            w = camera.Width.GetMax()
            h = camera.Height.GetMax()
            camera.DeInit()
            size = int(w * h)

            #
            del w; del h
            del camera
            cameras.Clear()
            del cameras
            system.ReleaseInstance()
            del system

            return mp.Array('i', size)

        # NOTE - If the above code block fails, the buffer size defaults to 25
        # million pixels which should support up to the 244S8 Blackfly S USB3
        except PySpin.SpinnakerException:
            return mp.Array('i', 25 * 1000000)

class VideoStream(MainProcess):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__(device)

        # override the child process class specification
        self._childClass = ChildProcessStreaming

        # initialize the camera and open the stream
        self.open()

        return

    def open(self):
        """
        """

        # spawn a child process as needed
        if self._child == None:
            self._initialize()

        # return if the stream is already open
        if self._child.acquiring.value:
            return

        # set the acquisition flag
        self._child.acquiring.value = 1

        def f(obj, camera, *args, **kwargs):

            # unpack the kwargs
            shape = kwargs['shape']

            # size of the image (i.e., total number of pixels)
            size = shape[0] * shape[1]

            try:
                camera.BeginAcquisition()

                # main acquisition loop
                while obj.acquiring.value:

                    try:
                        image = camera.GetNextImage(1)
                    except PySpin.SpinnakerException:
                        continue

                    #
                    if not image.IsIncomplete():

                        # convert the image
                        data = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray().flatten()

                        # store the image (critical - use lock)
                        with obj.buffer.get_lock():
                            obj.buffer[:size] = data

                return True

            except:
               return False

        # pack the kwargs
        kwargs = {'shape' : (self.height, self.width)}
        item = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)

        self._locked = True

        return

    def close(self):
        """
        """

        # return if there is no active child or the stream is already closed
        if self._child == None or self._child.acquiring.value == 0:
            return

        self._child.acquiring.value = False

        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'acquisition for camera[{self._device}] failed')

        def f(obj, camera, *args, **kwargs):
            try:
                camera.EndAcquisition()
                return True
            except:
                return False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'video deacquisition for camera[{self._device}] failed')

        self._locked = False

        # release the camera
        self._release()

        return

    def read(self):
        """
        """

        # return if there is no active child or the stream is closed
        if self._child == None or self._child.acquiring.value == 0:
            return

        # the lock blocks if a new image is being written to the image attribute
        with self._child.buffer.get_lock():
            data = self._child.buffer[:][:self.width * self.height]
            image = np.array(data, dtype=np.uint8).reshape([self.height, self.width])

        return (True, image)
