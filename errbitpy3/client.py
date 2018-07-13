import logging
import threading
import traceback
import sys
from django.conf import settings

app_name='AgrichainAPI'
version='0.0.1'

def log_error(method):
    def wrap_error(*args, **kwargs):
        try:
            if len(kwargs):
                method(**kwargs)
            else:
                method(*args)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.ERROR)
            logger.exception(e)

    wrap_error.__name__ = method.__name__
    return wrap_error

class ThreadedRequest(threading.Thread):
    def __init__(self, url, message, headers):
        super(ThreadedRequest, self).__init__()
        self.url = url
        self.message = message
        self.headers = headers

    @log_error
    def run(self):
        from urllib.request import urlopen
        import urllib.error
        try:
            response = urlopen(self.url, self.message, 20)
            status = response.getcode()
        except urllib.error.HTTPError as e:
            status = e.code

        if status == 200:
            return

        exceptionMessage = "Unexpected status code {0}".format(str(status))

        if status == 403:
            exceptionMessage = "Unable to send using SSL"
        elif status == 422:
            exceptionMessage = "Invalid XML sent"
        elif status == 500:
            exceptionMessage = "Destination server is unavailable. Please check the remote server status."
        elif status == 503:
            exceptionMessage = "Service unavailable. You may be over your quota."

        raise Exception(exceptionMessage)

class ErrbitClient:
    def __init__(self, service_url, api_key, component, node, environment):
        self.service_url = service_url
        self.api_key = api_key
        self.component_name = component
        self.node_name = node
        self.environment = environment

    @log_error
    def log(self, exception):
        message = self._generate_xml(exception, sys.exc_info()[2])
        self._sendMessage(message.encode('utf-8'))

    def _sendHttpRequest(self, headers, message):
        t = ThreadedRequest(self.service_url, message, headers)
        t.start()

    def _sendMessage(self, message):
        headers = {"Content-Type": "text/xml"}
        self._sendHttpRequest(headers, message)

    def _generate_xml(self, exc, trace):
        import traceback
        _trace_str = ''
        for filename, line_number, function_name, text in traceback.extract_tb(trace):
            _trace_str += '<line number="' + str(line_number) + '" file="' +filename+ '" method="' + function_name + ': ' + text + '" />'
        current_user_email = settings.current_user.email if getattr(settings, 'current_user', None) else ''

        return '<?xml version="1.0" encoding="UTF-8"?> <notice version="2.4"> <api-key>'+self.api_key+'</api-key> <notifier> <name>Blockgrain API</name> <version>0.0.0</version></notifier> <framework>Djangov2</framework> <error> <class>'+exc.__class__.__name__+'</class> <message><![CDATA['+', '.join(exc.args)+']]></message> <backtrace> '+_trace_str+' </backtrace> </error> <request> <component>'+self.component_name+'</component>  <cgi-data>  </cgi-data> </request> <server-environment> <project-root>/code</project-root> <environment-name>'+self.environment+'</environment-name> </server-environment> <current-user>'+current_user_email+'</current-user> </notice>'

