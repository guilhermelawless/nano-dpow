import os
import socket
import stat
import errno


def get_socket(path: str):
    # Adapted from https://github.com/aio-libs/aiohttp/issues/4155#issuecomment-539640591
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        if stat.S_ISSOCK(os.stat(path).st_mode):
            os.remove(path)
    except FileNotFoundError:
        pass

    try:
        sock.bind(path)
    except OSError as exc:
        sock.close()
        if exc.errno == errno.EADDRINUSE:
            msg = f'Address {path!r} is already in use'
            raise OSError(errno.EADDRINUSE, msg) from None
        else:
            raise
    except:
        sock.close()
        raise

    os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)
    return sock
