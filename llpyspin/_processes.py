import dill
import types
import queue
import PySpin
import logging
import numpy as np
import multiprocessing as mp

# shared flags
ACQUIRING = mp.Value('i', 0)

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.INFO)

class CameraBase(mp.Process):
    """
    """

    def __init__(self, device=0, **kwargs):
        """
        """

        # device ID
        self._device = device

        # input queue
        if 'iq' in kwargs.keys():
            self._iq = kwargs['iq']
        else:
            self._iq = mp.Queue()

        # output queue
        if 'oq' in kwargs.keys():
            self._oq = kwargs['oq']
        else:
            self._oq = mp.Queue()

        # started flag
        if 'started' in kwargs.keys():
            self._started = kwargs['started']
        else:
            self._started = mp.Value('i', 0)

        # acquiring flag
        if 'aqcuiring' in kwargs.keys():
            self._acquiring = kwargs['acquiring']
        else:
            self._acquiring = ACQUIRING

        #
        # self._container = mp.Array('i', [0])
        self._manager = mp.Manager()
        self._container = self._manager.list()
        self._lock = self._manager.Lock()

        #
        # self._lock = mp.Lock()

        # parameters (determined during initialization)
        self._framerate = None
        self._exposure  = None
        self._binsize   = None
        self._roi       = None

        # initialize the camera
        self.initialize()

        return

    def run(self):
        """
        """

        try:

            # create instances of the system and cameras list
            system  = PySpin.System.GetInstance()
            cameras = system.GetCameras()

            #
            assert len(cameras) != 0

            # instantiate the camera
            if type(self._device) == str:
                camera = cameras.GetBySerial(self._device)

            if type(self._device) == int:
                camera = cameras.GetByIndex(self._device)

        except:

            # clean-up
            try:
                del camera
            except NameError:
                pass
            cameras.Clear()
            del cameras
            system.ReleaseInstance()
            del system

            logging.log(logging.ERROR, f'failed to acquire camera[{self._device}]')

            # reset the started flag
            self.started = False

            return

        # main loop
        while self.started:

            try:

                # retrieve an item from the queue
                item = self._iq.get(block=False)

                # function with args, kwargs, or access to the namespace
                if type(item) == list or type(item) == tuple:

                    # unpickle the function
                    dilled, args, kwargs = item
                    f = dill.loads(dilled)

                    #
                    if type(kwargs) != dict:
                        kwargs = {kwarg : self.__dict__[kwarg] for kwarg in kwargs}
                        result = f(camera, *args, **kwargs)

                    #
                    else:
                        result = f(camera, *args, **kwargs)

                # function without args, kwargs, or access to the namespace
                elif type(item) == bytes:
                    f = dill.loads(item)
                    result = f(camera)

                #
                else:
                    pass

                # return the result
                self._oq.put(result)

            except queue.Empty:
                continue

        # clean up
        try:
            del camera
        except NameError:
            pass
        cameras.Clear()
        del cameras
        system.ReleaseInstance()
        del system

        return

    def initialize(self):
        """
        """

        #
        super().__init__()

        # set the started flag to True
        self.started = True

        if not self.is_alive():
            self.start()

        def f(camera):
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
                camera.AcquisitionFrameRate.SetValue(1)

                #
                x = camera.OffsetX.GetValue()
                y = camera.OffsetY.GetValue()
                w = camera.Width.GetValue()
                h = camera.Height.GetValue()

                #
                roi = (x, y, w, h)
                framerate = int(np.around(camera.AcquisitionFrameRate.GetValue()))
                exposure  = int(np.around(camera.ExposureTime.GetValue()))
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

        # send the function through the queue
        self._iq.put(dill.dumps(f))

        # retrieve the result of the function call
        result, parameters = self._oq.get()
        if result:
            logging.log(logging.INFO, f'camera[{self._device}] initialized')
            self._framerate = parameters['framerate']
            self._exposure  = parameters['exposure']
            self._binsize   = parameters['binsize']
            self._roi       = parameters['roi']
        else:
            logging.log(logging.ERROR, f'failed to initialize camera[{self._device}]')

        return

    def release(self):
        """
        """

        if not self.started:
            return

        def f(camera):
            try:
                if camera.IsStreaming():
                    camera.EndAcquisition()
                camera.DeInit()
                return True
            except PySpin.SpinnakerException:
                return False

        # send the function through the queue
        self._iq.put(dill.dumps(f))

        # retrieve the result of the function call
        result = self._oq.get()
        if result:
            logging.log(logging.INFO, f'camera[{self._device}] released')
        else:
            logging.log(logging.ERROR, f'failed to release camera[{self._device}]')

        # clean up
        self.join()

        return

    def join(self):
        """
        override the join method and add some additional functionality
        """

        # break out of the main loop
        self.started = False

        # join the thread
        super().join(timeout=5)

        # check if it has deadlocked
        if self.is_alive():
            logging.log(logging.ERROR, 'child process deadlocked')
            self.terminate()

        return

    # framerate
    @property
    def framerate(self):

        def f(camera):
            return camera.AcquisitionFrameRate.GetValue()

        self._iq.put(dill.dumps(f))
        value = int(np.around(self._oq.get()))

        #
        if value != self._framerate:
            logging.log(logging.ERROR, f'actual camera framerate of {value} fps does not equal the target framerate of {self._framerate} fps')
            return

        return value

    @framerate.setter
    def framerate(self, value):

        def f(camera, value):
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
        args = [value]
        item = (dill.dumps(f), args, {})
        self._iq.put(item)

        #
        result = self._oq.get()
        if result:
            self._framerate = value
            logging.log(logging.INFO, f'camera[{self._device}] framerate set to {value}')
        else:
            logging.log(logging.ERROR, f'failed to set camera[{self._device}] framerate to {value}')

        return

    # exposure
    @property
    def exposure(self):

        def f(camera):
            return camera.ExposureTime.GetValue()

        self._iq.put(dill.dumps(f))
        value = int(np.around(self._oq.get()))

        #
        if value != self._exposure:
            logging.log(logging.ERROR, f'actual camera exposure of {value} us does not equal the target exposure of {self._exposure} us')
            return

        return value

    # binsize
    @property
    def binsize(self):

        def f(camera):
            x = camera.BinningHorizontal.GetValue()
            y = camera.BinningVertical.GetValue()
            return (x, y)

        self._iq.put(dill.dumps(f))
        value = self._oq.get()

        #
        if value != self._binsize:
            logging.log(logging.ERROR, f'actual camera binsize of {value} pixels does not equal the target binsize of {self._binsize} pixels')
            return

        return value

    # roi
    @property
    def roi(self):

        def f(camera):
            x = camera.OffsetX.GetValue()
            y = camera.OffsetY.GetValue()
            w = camera.Width.GetValue()
            h = camera.Height.GetValue()
            return (x, y, w, h)

        self._iq.put(dill.dumps(f))
        value = self._oq.get()

        #
        if value != self._roi:
            logging.log(logging.ERROR, f'actual camera roi parameters ({value}) do not equal the target parameters of {self._roi}')
            return

        return value

    # width
    @property
    def width(self):
        x, y, w, h = self.roi
        return w

    # height
    @property
    def height(self):
        x, y, w, h = self.roi
        return h

    # started flag which maintains the main loop
    @property
    def started(self):
        return True if self._started.value == 1 else False

    @started.setter
    def started(self, flag):
        if flag not in [0, 1, True, False]:
            raise ValueError('started flag can only be set to 0, 1, True, or False')
        self._started.value = 1 if flag == True else 0

    # acquiring flag which maintains the acquisition loop
    @property
    def acquiring(self): return True if self._acquiring.value == 1 else False

    @acquiring.setter
    def acquiring(self, value):
        self._acquiring.value = 1 if value == True else False

    # acquisition lock state
    @property
    def locked(self):
        return True if self._lock.locked() else False

    @locked.setter
    def locked(self, value):

        # engage the lock
        if value == True:
            if self.locked:
                logging.log(logging.INFO, 'acquisition lock is already engaged')
                return
            result = self._lock.acquire(block=False)
            if result:
                logging.log(logging.INFO, 'acquisition lock engaged')
            else:
                logging.log(logging.WARNING, 'failed to engage acquisition lock')

        # disengage the lock
        elif value == False:
            if not self.locked:
                logging.log(logging.INFO, 'acquisition lock is not engaged')
                return
            try:
                self._lock.release()
                logging.log(logging.INFO, 'acquisition lock disengaged')
            except ValueError:
                logging.log(logging.WARNING, 'failed to disengage acquisition lock')

        else:
            raise ValueError('invalid acquisition lock state')
