from urllib.request import Request, urlopen


FAKE_UA = 'Mozilla/5.0 (X11; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0'


def download_file(url, fileobj):
    request = Request(url)
    request.add_header('User-Agent', FAKE_UA)
    response = urlopen(request)
    copy_to(response, fileobj)


def copy_to(src, dest):
    while True:
        data = src.read(8192)
        if not data:
            break
        dest.write(data)