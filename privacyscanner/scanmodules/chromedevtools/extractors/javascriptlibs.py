from ..utils import JavaScriptError, javascript_evaluate
from .base import Extractor


LIBRARY_JS = """
(function() {
    return {
        'jQuery': typeof(jQuery) !== 'undefined' ? jQuery.fn.jquery : null,
        'React': typeof(React) !== 'undefined' ? React.version : null,
        'AngularJS': typeof(angular) !== 'undefined' ? angular.version.full : null
    };
})()
"""


class JavaScriptLibsExtractor(Extractor):
    def extract_information(self):
        versions = {
            'jQuery': None,
            'React': None,
            'AngularJS': None
        }
        try:
            versions.update(javascript_evaluate(self.page.tab, LIBRARY_JS))
        except JavaScriptError:
            pass
        self.result['javascript_libraries'] = versions
