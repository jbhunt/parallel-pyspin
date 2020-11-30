import dill
import types
import queue
import PySpin
import logging
import numpy as np
import multiprocessing as mp

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

# this is the acquisition flag shared among all cameras
_ACQUIRING = mp.Value('i', 0)

class AcquisitionPropertyError(Exception):
    """
    """

    def __init__(self, message):
        """
        """

        super().__init__(message)

        return

class ChildProcessError(Exception):
    """
    """

    def __init__(self, message):
        """
        """

        super().__init__(message)

        return

class ChildProcess(mp.Process):
    """
    """

    def __init__(self, device=0):
        """
        """

        super().__init__()

        self._device   = device
        self._nickname = f'camera[{device}]'

        # io queues
        self.iq = mp.Queue()
        self.oq = mp.Queue()

        #
        self.started   = mp.Value('i', 0)
        self.acquiring = _ACQUIRING

        return

    def start(self):
        """
        override the start method
        """

        self.started.value = 1

        super().start()

    def join(self, timeout=0):
        """
        override the join method
        """

        self.started.value = 0

        super().join(timeout)

        return

    def run(self):
        """
        """

        try:

            # create instances of the system and cameras list
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()

            # instantiate the camera
            if type(self._device) == str:
                camera = cameras.GetBySerial(self._device)

            if type(self._device) == int:
                camera = cameras.GetByIndex(self._device)

            #
            result = True
            self.oq.put(result)

        except PySpin.SpinnakerException:

            # clean-up
            try:
                del camera
            except NameError:
                pass
            cameras.Clear()
            del cameras
            try:
                system.ReleaseInstance()
            except PySpin.SpinnakerException:
                pass
            del system

            # reset the started flag
            self.started.value = 0

            #
            result = False
            self.oq.put(result)

            return

        # main loop
        while self.started.value:

            try:

                # input
                item = self.iq.get(block=False)

                # call the function
                dilled, args, kwargs = item
                f = dill.loads(dilled)
                result = f(self, camera, *args, **kwargs)

                # output
                self.oq.put(result)

            except queue.Empty:
                continue

        # clean-up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        del cameras
        try:
            system.ReleaseInstance()
        except PySpin.SpinnakerException:
            pass
        del system

        return

class MainProcess(object):
    """
    this class houses the interface with the child process
    """

    def __init__(self, device):
        """
        """

        super().__init__()

        # device index or serial no
        self._device = device

        # parameters (determined during initialization)
        self._framerate = None
        self._exposure  = None
        self._binsize   = None
        self._roi       = None

        # acquisition lock state
        self._locked = False

        # default class for the child process
        self._child = None
        self._childClass = ChildProcess

        return

    def _initialize(self):
        """
        """

        # create and start the child process
        self._child = self._childClass(self._device)
        self._child.start()
        result = self._child.oq.get()
        if not result:
            self._child.join()
            self._child = None
            raise ChildProcessError('failed to initialize child process')

        def f(obj, camera, *args, **kwargs):
            try:

                #
                camera.Init()

                #
                camera.PixelFormat.SetValue(PySpin.PixelFormat_Mono8)
                camera.AcquisitionMode.SetValue(PySpin.AcquisitionMode_Continuous)
                camera.TLStream.StreamBufferHandlingMode.SetValue(PySpin.StreamBufferHandlingMode_NewestOnly)

                # set the exposure
                camera.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
                camera.AcquisitionFrameRateEnable.SetValue(False)
                camera.ExposureTime.SetValue(3000)

                # set the framerate
                camera.AcquisitionFrameRateEnable.SetValue(True)
                camera.AcquisitionFrameRate.SetValue(10)

                # set the binsize
                camera.BinningHorizontal.SetValue(2)
                camera.BinningVertical.SetValue(2)

                #
                x = camera.OffsetX.GetValue()
                y = camera.OffsetY.GetValue()
                w = camera.Width.GetValue()
                h = camera.Height.GetValue()

                #
                roi = (x, y, w, h)
                framerate = int(np.ceil(camera.AcquisitionFrameRate.GetValue()))
                exposure  = int(np.ceil(camera.ExposureTime.GetValue()))
                binsize   = (camera.BinningHorizontal.GetValue(), camera.BinningVertical.GetValue())

                #
                parameters = {
                    'framerate' : framerate,
                    'exposure'  : exposure,
                    'binsize'   : binsize,
                    'roi'       : roi,
                }

                return True, parameters

            except PySpin.SpinnakerException:
                return False, None

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, parameters = self._child.oq.get()

        # set all property values
        if result:
            self._framerate = parameters['framerate']
            self._exposure  = parameters['exposure']
            self._binsize   = parameters['binsize']
            self._height    = parameters['roi'][3]
            self._width     = parameters['roi'][2]
            self._roi       = parameters['roi']
        else:
            print('hello world')

        return

    def _release(self):
        """
        """

        if not self._child.started.value:
            logging.log(logging.DEBUG, 'no active child process')
            return

        def f(obj, camera, *args, **kwargs):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                camera.DeInit()
                return True
            except PySpin.SpinnakerException:
                return False

        # send the function through the queue
        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)

        # retrieve the result of the function call
        result = self._child.oq.get()

        # join the child process with the main process
        try:
            self._child.join(timeout=3)
        except mp.TimeoutError:
            self._child.terminate()
            raise ChildProcessError('child process dead-locked')
        self._child = None

        if result:
            logging.log(logging.INFO, f'camera[{self._device}] released')
        else:
            logging.log(logging.ERROR, f'failed to release camera[{self._device}]')


    # framerate
    @property
    def framerate(self):

        if self.locked:
            return self._framerate

        def f(obj, camera, *args, **kwargs):
            try:
                value = camera.AcquisitionFrameRate.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return False, None

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, value = self._child.oq.get()

        #
        if not result:
            logging.log(logging.ERROR, f'framerate query failed')
        else:
            return int(np.ceil(value))
        if int(np.ceil(value)) != self._framerate:
            logging.log(logging.ERROR, f'actual camera framerate of {value} fps does not equal the target framerate of {self._framerate} fps')

    @framerate.setter
    def framerate(self, value):

        if self.locked:
            raise AcquisitionPropertyError(f'acquisition lock is engaged')

        def f(obj, camera, *args, **kwargs):
            value = kwargs['value']
            if not camera.AcquisitionFrameRateEnable.GetValue():
                camera.AcquisitionFrameRateEnable.SetValue(True)
            min = camera.AcquisitionFrameRate.GetMin()
            max = camera.AcquisitionFrameRate.GetMax()
            if not min <= value <= max:
                return False
            else:
                try:
                    camera.AcquisitionFrameRate.SetValue(value)
                    if int(np.around(camera.AcquisitionFrameRate.GetValue())) != value:
                        return False
                    else:
                        return True
                except PySpin.SpinnakerException:
                    return False

        #
        kwargs = {'value' : value}
        item   = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)
        result = self._child.oq.get()

        if not result:
            logging.log(logging.ERROR, f'failed to set camera[{self._device}] framerate to {value}')
        else:
            self._framerate = value

        return

    # exposure
    @property
    def exposure(self):

        if self.locked:
            return self._exposure

        def f(obj, camera, *args, **kwargs):
            try:
                value = camera.ExposureTime.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return False, None

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, value = self._child.oq.get()

        #
        if not result:
            logging.log(logging.ERROR, f'failed to get exposure value from camera[{self._device}]')
        else:
            return int(np.ceil(value))

    @exposure.setter
    def exposure(self, value):

        if self.locked:
            raise AcquisitionPropertyError(f'acquisition lock is engaged')

        def f(obj, camera, *args, **kwargs):
            value = kwargs['value']
            try:
                min = camera.ExposureTime.GetMin()
                max = camera.ExposureTime.GetMax()
                if not min <= value <= max:
                    return False
                else:
                    camera.ExposureTime.SetValue(value)
                    return True

            except PySpin.SpinnakerException:
                return False

        item = (dill.dumps(f), [], {'value' : value})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to set exposure to {value} us for camera[{self._device}]')
        else:
            self._exposure = value

        return

    # binsize
    @property
    def binsize(self):

        if self.locked:
            return self._binsize

        def f(obj, camera, *args, **kwargs):
            try:
                x = camera.BinningHorizontal.GetValue()
                y = camera.BinningVertical.GetValue()
                return True, (x, y)
            except PySpin.SpinnakerException:
                return False, None

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, value = self._child.oq.get()

        #
        if not result:
            logging.log(logging.ERROR, f'failed to query exposure for camera[{self._device}]')
        else:
            return value

    @binsize.setter
    def binsize(self, value):

        # check the value of the target binsize

        # it can be a single integer
        if type(value) == int:
            if value not in [1, 2, 4]:
                raise AcquisitionPropertyError('binsize must be 1, 2, or 4 pixels')
            value = (value, value)

        # it can be a list or tuple of two integers
        elif (type(value) == list or type(value) == tuple) and len(value) == 2:
            for item in value:
                if item not in [1, 2, 4]:
                    raise AcquisitionPropertyError('binsize must be 1, 2, or 4 pixels')

        # it can't be anything else
        else:
            raise AcquisitionPropertyError(f'{value} is not a valid value for the binsize property')

        def f(obj, camera, *args, **kwargs):
            xbin, ybin = kwargs['value']
            try:
                xmin = camera.BinningHorizontal.GetMin()
                xmax = camera.BinningHorizontal.GetMax()
                ymin = camera.BinningVertical.GetMin()
                ymax = camera.BinningVertical.GetMax()
                if not (xmin <= xbin <= xmax) or (not ymin <= ybin <= ymax):
                    return False
                else:
                    camera.BinningHorizontal.SetValue(xbin)
                    camera.BinningVertical.SetValue(ybin)
                    camera.OffsetX.SetValue(0)
                    camera.OffsetY.SetValue(0)
                    camera.Height.SetValue(camera.Height.GetMax())
                    camera.Width.SetValue(camera.Width.GetMax())
                    return True

            except PySpin.SpinnakerException:
                return False

        item = (dill.dumps(f), [], {'value' : value})
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to set binsize to {value} pixels for camera[{self._device}]')
        else:
            self._binsize = value

        return

    # roi
    @property
    def roi(self):

        if self.locked:
            return self._roi

        def f(obj, camera, *args, **kwargs):
            x = camera.OffsetX.GetValue()
            y = camera.OffsetY.GetValue()
            w = camera.Width.GetValue()
            h = camera.Height.GetValue()
            return (x, y, w, h)

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        value = self._child.oq.get()

        #
        if value != self._roi:
            logging.log(logging.ERROR, f'actual camera roi parameters ({value}) do not equal the target parameters of {self._roi}')
            return

        return value

    @roi.setter
    def roi(self, value):

        if self.locked:
            raise AcquisitionPropertyError('acquisition lock is engaged')

        if (type(roi) != list and type(roi) != tuple) or len(roi) != 4:
            raise AcquisitionPropertyError(f'{value} is not a valid value for the roi property')

        def f(obj, camera, *args, **kwargs):
            x, y, w, h = kwargs['value']
            try:
                if (camera.Width.GetMax() - (x + w) <= 0) or (camera.Height.GetMax() - (y + h) <= 0):
                    return False
                else:
                    camera.OffsetX.SetValue(x)
                    camera.OffsetY.SetValue(y)
                    camera.Height.SetValue(h)
                    camera.Width.SetValue(w)
                    return True

            except PySpin.SpinnakerException:
                return False

        kwargs = {'value' : value}
        item = (dill.dumps(f), [], kwargs)
        self._child.iq.put(item)
        result = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to set the roi parameters to {value} for camera[{self._device}]')
        else:
            self._roi = value

        return

    # width (read-only)
    @property
    def width(self):

        if self.locked:
            return self._width

        def f(obj, camera, *args, **kwargs):
            try:
                value = camera.Width.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return None, False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, value = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to query frame width for camera [{self._device}]')
        else:
            return value

    # height (read-only)
    @property
    def height(self):

        if self.locked:
            return self._height

        def f(obj, camera, *args, **kwargs):
            try:
                value = camera.Height.GetValue()
                return True, value
            except PySpin.SpinnakerException:
                return None, False

        item = (dill.dumps(f), [], {})
        self._child.iq.put(item)
        result, value = self._child.oq.get()
        if not result:
            logging.log(logging.ERROR, f'failed to query frame height for camera [{self._device}]')
        else:
            return value

    # acquisition lock state
    @property
    def locked(self):
        return self._locked

    # camera nickname
    @property
    def nickname(self):
        return self._nickname

    @nickname.setter
    def nickname(self, value):
        self._nickname = str(value)
