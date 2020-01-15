import base64

from privacyscanner.scanmodules.chromedevtools.extractors.base import Extractor


INSTRUMENTATION_JS = """
function instrumentFunction(func, name, log_type) {
    return function() {
        let retval = func.apply(this, arguments);
        log(log_type, {
            'type': 'function',
            'name': name,
            'arguments': Array.prototype.slice.call(arguments),
            'retval': retval
        });
    }
}

function instrumentProperty(obj, name, prop, log_type) {
    let prototype = obj;
    let descriptor;
    do {
        descriptor = Object.getOwnPropertyDescriptor(prototype, prop);
        if (typeof(descriptor) !== 'undefined') {
            break
        }
        prototype = Object.getPrototypeOf(prototype);
    } while (prototype !== null);

    if (typeof(descriptor) === 'undefined') {
        return;
    }

    let origGetter = descriptor.get;
    let origSetter = descriptor.set;
    
    Object.defineProperty(obj, prop, {
        get: function() {
            let value = origGetter.apply(this, arguments);
            log(log_type, {
                'type': 'property',
                'name': name,
                'value': value,
                'access': 'get'
            });
            return value;
        },
        set: function() {
            log(log_type, {
                'type': 'property',
                'name': name,
                'value': arguments[0],
                'access': 'set'
            });
            return origSetter.apply(this, arguments);
            
        }
    });
}

function instrumentObject(obj, name, properties, log_type) {
    for (let i = 0; i < properties.length; i++) {
        let prop = properties[i];
        if (typeof(obj[prop]) === 'function') {
            let funcName = name + '.' + prop;
            obj[prop] = instrumentFunction(obj[prop], funcName, log_type);
        } else {
            let propName = name + '.' + prop;
            instrumentProperty(obj, prop, propName, log_type);
        }
    }
}

instrumentObject(window.HTMLCanvasElement.prototype,
                'HTMLCanvasElement',
                ['toDataURL'],
                'fingerprinting:canvas');
instrumentObject(window.CanvasRenderingContext2D.prototype,
                 'CanvasRenderingContext2D',
                 ['fillText', 'strokeText'],
                 'fingerprinting:canvas');
instrumentObject(window.AudioContext.prototype,
                 'AudioContext',
                 ['createAnalyser'],
                 'fingerprinting:audio');
instrumentObject(window.WebGLRenderingContext.prototype,
                 'WebGLRenderingContext',
                 ['readPixels', 'getParameter'],
                 'fingerprinting:webgl');
instrumentObject(localStorage,
                 'localStorage',
                 ['setItem', 'getItem'],
                 'fingerprinting:misc');
instrumentObject(sessionStorage,
                 'sessionStorage',
                 ['setItem', 'getItem'],
                 'fingerprinting:misc');
instrumentProperty(window.Navigator.prototype,
                 'userAgent',
                 ['userAgent'],
                 'fingerprinting:misc');
instrumentProperty(window.Navigator.prototype,
                 'language',
                 ['language'],
                 'fingerprinting:misc');
instrumentProperty(window.Navigator.prototype,
                 'languages',
                 ['languages'],
                 'fingerprinting:misc');
instrumentProperty(window.Screen.prototype,
                 'colorDepth',
                 ['colorDepth'],
                 'fingerprinting:misc');
"""


class FingerprintingExtractor(Extractor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._canvas = {'calls': [], 'is_fingerprinting': False}
        self._audio = {'calls': [], 'is_fingerprinting': False}
        self._webgl = {'calls': [], 'is_fingerprinting': False}
        self._misc = {'calls': [], 'is_fingerprinting': False}
        self._canvas_call_stack = None
        self._audio_call_stack = None
        self._webgl_call_stack = None
        self._misc_call_stack = None
        self._canvas_image = None

    def extract_information(self):
        self.result['fingerprinting'] = {
            'canvas': self._canvas,
            'audio': self._audio,
            'webgl': self._webgl,
            'misc': self._misc,
        }
        self._extract_canvas()

    def register_javascript(self):
        return INSTRUMENTATION_JS

    def receive_log(self, log_type, message, call_stack):
        if log_type == 'fingerprinting:canvas':
            self._receive_canvas_log(message, call_stack)
        if log_type == 'fingerprinting:audio':
            self._receive_audio_log(message, call_stack)
        if log_type == 'fingerprinting:webgl':
            self._receive_webgl_log(message, call_stack)
        if log_type == 'fingerprinting:misc':
            self._receive_misc_log(message, call_stack)

    def _extract_canvas(self):
        uses_text = False
        text_methods = ('CanvasRenderingContext2D.fillText',
                        'CanvasRenderingContext2D.strokeText')
        for call in self._canvas['calls']:
            if call['method'] in text_methods:
                uses_text = True
                break
        if uses_text and self._canvas_call_stack is not None:
            self._canvas['is_fingerprinting'] = True
            self._canvas['call_stack'] = self._canvas_call_stack
            content = None
            try:
                info_part, data_part = self._canvas_image.split(',', 1)
                if 'base64' in info_part:
                    content = base64.b64decode(data_part)
            except ValueError:
                pass
            if content:
                self.result.add_file('fingerprinting_canvas', content)
        if self._audio_call_stack is not None:
            self._audio['is_fingerprinting'] = True
            self._audio['call_stack'] = self._audio_call_stack
        if self._webgl_call_stack is not None:
            self._webgl['is_fingerprinting'] = True
            self._webgl['call_stack'] = self._webgl_call_stack
        if self._misc_call_stack is not None:
            self._misc['is_fingerprinting'] = True
            self._misc['call_stack'] = self._misc_call_stack

    def _receive_canvas_log(self, message, call_stack):
        self._canvas['calls'].append({
            'method': message['name'],
            'arguments': message['arguments']
        })
        if message['name'] == 'HTMLCanvasElement.toDataURL':
            # Our first element is the function that was used to override
            # the original function for logging, i.e., that anonymous
            # function returned by instrumentFunction. So we skip it in our
            # call stack because it provides no value.
            self._canvas_call_stack = call_stack[1:]
            self._canvas_image = message['retval']

    def _receive_audio_log(self, message, call_stack):
        calldict = {
            'method': message['name'],
            'arguments': message['arguments']
        }
        if calldict not in self._audio['calls']:
            self._audio['calls'].append(calldict)
        # self._audio_call_stack = call_stack

    def _receive_webgl_log(self, message, call_stack):
        calldict = {
            'method': message['name'],
            'arguments': message['arguments']
        }
        if calldict not in self._webgl['calls']:
            self._webgl['calls'].append(calldict)
        # self._webgl_call_stack = call_stack

    def _receive_misc_log(self, message, call_stack):
        listofcheckedproperties = ['userAgent', 'language', 'languages', 'colorDepth']
        if message['name'] in listofcheckedproperties:
            calldict = {
                'property': message['name'],
                'value': message['value']
            }
        elif 'arguments' in message.keys():
            calldict = {
                'method': message['name'],
                'arguments': message['arguments']
            }
        if calldict not in self._misc['calls']:
            self._misc['calls'].append(calldict)
        # self._misc_call_stack = call_stack
