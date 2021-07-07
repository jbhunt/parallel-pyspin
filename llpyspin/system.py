from .primary import PrimaryCamera
from .secondary import SecondaryCamera

class AcquisitionSystem():
    """
    """

    def __init__(self,
        working_directory : str,
        primary_device    : int=0,
        secondary_devices : list=[],
        ):
        """
        Keywords
        --------
        working_directory
            Working directory where the movie files are saved
        primary_device
            Device index or serial number for the primary camera
        secondary_devices
            A list of device indices or serial numbers for all secondary cameras
        """

        self.primary_camera = PrimaryCamera(primary_device)
        self.secondary_cameras = [
            SecondaryCamera(device) for device in secondary_devices
        ]

        return

    def start_video_recording(self):
        """
        Start acquisition
        """

        return

    def stop_video_recording(self):
        """
        Stop acquisition
        """

        return
