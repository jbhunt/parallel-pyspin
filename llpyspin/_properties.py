import logging

# constants
from ._constants import *

# logging setup
logging.basicConfig(format='%(levelname)s : %(message)s',level=logging.DEBUG)

class AcquisitionProperty(object):
    """
    a minimal implementation of descriptors with the additional functionality
    to handle intermitent interruption of acquisition during changes in property
    values


    references
    ----------
    [1] https://docs.python.org/3/howto/descriptor.html#properties
    """


    def __init__(self, fget=None, fset=None, fdel=None, doc=None):
        self.fget   = fget
        self.fset   = fset
        self.fdel   = fdel
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(obj)

    def __set__(self, obj, value):
        """
        """

        if self.fset is None:
            raise AttributeError("can't set attribute")

        # pause acquiition
        try:
            assert obj.acquiring == False
            restart = False

        except AssertionError:
            logging.debug('pausing acquisition')
            obj.acquiring = False
            result = obj._oq.get()
            if not result: logging.debug('video acquisition failed')
            obj._iq.put(STOP)
            result = obj._oq.get()
            if not result: logging.debug('video de-acquisition failed')
            restart = True

        # call the fset method
        self.fset(obj, value)

        # restart acquisition
        if restart:
            logging.debug('unpausing acquisition.')
            obj.acquiring = True
            obj._iq.put(START)

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)

    def getter(self, fget):
        return type(self)(fget, self.fset, self.fdel, self.__doc__)

    def setter(self, fset):
        return type(self)(self.fget, fset, self.fdel, self.__doc__)

    def deleter(self, fdel):
        return type(self)(self.fget, self.fset, fdel, self.__doc__)

class PropertiesMixin(object):
    """
    This mixin contains all the video acquisition property definitions.
    """

    def _setall(self):
        """
        set all properties to their current values
        """

        self.framerate = self._framerate
        self.exposure  = self._exposure
        self.binsize   = self._binsize

        return

    # framerate property
    @AcquisitionProperty
    def framerate(self): return self._framerate

    @framerate.setter
    def framerate(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(FRAMERATE_PROPERTY_ID) # tell the child what property is being set
        self._iq.put(value)

        logging.info(f'Setting framerate to {value} fps.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the framerate to "{value}" fps.')
            return

        self._framerate = value

        return

    # exposure
    @AcquisitionProperty
    def exposure(self): return self._exposure

    @exposure.setter
    def exposure(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(EXPOSURE_PROPERTY_ID) # tell the child what property is being set
        self._iq.put(value)

        logging.info(f'Setting exposure to {value} us.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the exposure to "{value}" us.')
            return

        self._exposure = value
        return

    # binsize
    @AcquisitionProperty
    def binsize(self): return self._binsize

    @binsize.setter
    def binsize(self, value):
        """
        """

        self._iq.put(SET)
        self._iq.put(BINSIZE_PROPERTY_ID)
        self._iq.put(value)

        logging.info(f'Setting binsize to {value} pixels.')

        result = self._oq.get()
        if not result:
            logging.warning(f'Failed to set the binsize to "{value}" pixel(s).')
            return

        self._binsize = value

        # reset the ROI parameters according to the new binsize
        self.roi = None

        return

    @AcquisitionProperty
    def roi(self):
        return self._roi

    @roi.setter
    def roi(self, value):
        """
        """

        # reset the ROI
        if value == None:

            # get width
            self._iq.put(GET)
            self._iq.put(WIDTH_PROPERTY_ID)
            width = self._oq.get()
            result = self._oq.get()

            # get width
            self._iq.put(GET)
            self._iq.put(HEIGHT_PROPERTY_ID)
            height = self._oq.get()
            result = self._oq.get()

            value = (0, 0, height, width)

        self._iq.put(SET)
        self._iq.put(ROI_PROPERTY_ID)
        self._iq.put(value)

        logging.info(f'setting the ROI parameters to {value}.')

        result = self._oq.get()
        if not result:
            logging.warning(f'failed to set the ROI parameters to {value}')
            return

        self._roi = value
