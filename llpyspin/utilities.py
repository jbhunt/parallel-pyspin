import PySpin

def camera_count():
    """
    Return the number of available cameras
    """

    system = PySpin.System.GetInstance()
    cameras = system.GetCameras()
    ncameras = len(cameras)
    cameras.Clear()
    del cameras
    system.ReleaseInstance()
    del system

    return ncameras
