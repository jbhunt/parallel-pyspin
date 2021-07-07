import dill
import queue
import PySpin
import logging
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

        # create a shared memory array for storing a single image
        # self.buffer = self._initialize_image_buffer(device)
        self.buffer = mp.Array('i', 10 * 1000000)

        #
        super().__init__(device)

        return

    def _initialize_image_buffer(self, device):
        """
        this method determines the size of the image buffer on instantiation
        """

        #
        try:
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()
            if type(device) == str:
                camera = cameras.GetBySerial(device)
            else:
                camera = cameras.GetByIndex(device)
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
        self._spawn_child_process()
        self.open()

        return

    def open(self):
        """
        """

        # spawn a child process as needed
        if self._child is None:
            self._spawn_child_process()
        else:
            raise CameraError('Video stream is already open')

        # set the acquisition flag
        self._child.acquiring.value = 1

        def f(child, camera, **kwargs):

            # unpack the shape of the image
            width, height = kwargs['shape']

            # size of the image (i.e., total number of pixels)
            size = width * height

            try:
                camera.BeginAcquisition()

                # main acquisition loop
                while child.acquiring.value:

                    try:
                        image = camera.GetNextImage(kwargs['timeout'])
                    except PySpin.SpinnakerException:
                        continue

                    #
                    if not image.IsIncomplete():

                        # convert the image
                        data = image.Convert(PySpin.PixelFormat_Mono8, PySpin.HQ_LINEAR).GetNDArray().flatten()

                        # store the image (critical - use lock)
                        with obj.buffer.get_lock():
                            obj.buffer[:size] = data

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
            raise CameraError('Video stream is not open')

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

        # grab the image currently loaded into the buffer
        try:

            # acquire the buffer object's lock
            with self._child.buffer.get_lock():
                data = self._child.buffer[:][:self.width * self.height]
                image = np.array(data, dtype=np.uint8).reshape([self.height, self.width])

            return (True, image)

        else:
            return (False, None)
