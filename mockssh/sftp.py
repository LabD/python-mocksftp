import logging
import os

import paramiko
from paramiko import SFTPAttributes

__all__ = [
    "SFTPServer",
]


class SFTPHandle(paramiko.SFTPHandle):

    log = logging.getLogger(__name__)

    def __init__(self, file_obj, flags=0):
        super(SFTPHandle, self).__init__(flags)
        self.file_obj = file_obj

    @property
    def readfile(self):
        return self.file_obj

    @property
    def writefile(self):
        return self.file_obj


def returns_sftp_error(func):

    LOG = logging.getLogger(__name__)

    def wrapped(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OSError as err:
            LOG.debug("Error calling %s(%s, %s): %s",
                      func, args, kwargs, err, exc_info=True)
            return SFTPServer.convert_errno(err.errno)
        except Exception as err:
            LOG.debug("Error calling %s(%s, %s): %s",
                      func, args, kwargs, err, exc_info=True)
            return paramiko.SFTP_FAILURE

    return wrapped


class SFTPServerInterface(paramiko.SFTPServerInterface):

    log = logging.getLogger(__name__)

    def __init__(self, server, *largs, **kwargs):
        self._root = kwargs.pop('root', None)
        super(SFTPServerInterface, self).__init__(server, *largs, **kwargs)

    def _path_join(self, path):
        return os.path.realpath(
            os.path.join(self._root, os.path.normpath(path)))

    def session_started(self):
        pass

    def session_ended(self):
        pass

    @returns_sftp_error
    def list_folder(self, path):
        path = self._path_join(path)
        result = []
        for filename in os.listdir(path):
            stat_data = os.stat(os.path.join(path, filename))
            item = SFTPAttributes.from_stat(stat_data)
            item.filename = filename
            result.append(item)
        return result

    @returns_sftp_error
    def mkdir(self, path, attr):
        path = self._path_join(path)
        os.mkdir(path)
        return paramiko.SFTP_OK

    @returns_sftp_error
    def rmdir(self, path):
        path = self._path_join(path)
        os.rmdir(path)
        return paramiko.SFTP_OK

    @returns_sftp_error
    def open(self, path, flags, attr):
        path = self._path_join(path)
        fd = os.open(path, flags)
        self.log.debug("open(%s): fd: %d", path, fd)
        if flags & (os.O_WRONLY | os.O_RDWR):
            mode = "w"
        elif flags & (os.O_APPEND):
            mode = "a"
        else:
            mode = "r"
        mode += "b"
        self.log.debug("open(%s): Mode: %s", path, mode)
        return SFTPHandle(os.fdopen(fd, mode), flags)

    @returns_sftp_error
    def stat(self, path):
        path = self._path_join(path)
        st = os.stat(path)
        return paramiko.SFTPAttributes.from_stat(st, path)


class SFTPServer(paramiko.SFTPServer):

    def __init__(self, channel, name, server, sftp_si=SFTPServerInterface,
                 *largs, **kwargs):
        kwargs["sftp_si"] = SFTPServerInterface
        super(SFTPServer, self).__init__(
            channel, name, server, *largs, **kwargs)
