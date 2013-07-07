###
# Copyright (c) 2007, Ali Afshar
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import select
import threading
import socket
import SocketServer


import supybot.world as world
from supybot.commands import *
from supybot.log import getPluginLogger
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks



class RequestHandler(SocketServer.StreamRequestHandler):

    def handle(self):
        # data should be: 'network channel message', e.g.
        # 'Freenode #geany blah blah'
        data = self.rfile.readline().strip()
        self.server.logger.debug(u'got data from socket: %s' % data)
        network, channel, message = data.split(' ', 2)
        ci = ControlInstance()
        ci.privmsg(network, channel, message)


class ControlInstance(object):

    def privmsg(self, network, personorchannel, message):
        target_irc, target = self._get_irc_and_target(network, personorchannel)
        msg = ircmsgs.privmsg(target, message)
        target_irc.sendMsg(msg)

    def _get_irc(self, network):
        for irc in world.ircs:
            if irc.network == network:
                return irc

    def _get_person_or_channel(self, irc, personorchannel):
        if personorchannel.startswith('#'):
            for channel in irc.state.channels:
                if channel == personorchannel:
                    return channel
        else:
            return personorchannel

    def _get_irc_and_target(self, network, personorchannel):
        target_irc = self._get_irc(network)
        if target_irc is None:
            raise Exception('Not on Network: %s' % network)
        target = self._get_person_or_channel(target_irc, personorchannel)
        if target is None:
            raise Exception('Not on Channel: %s' % personorchannel)
        return target_irc, target


class SocketServerImpl(SocketServer.TCPServer):

    timeout = None
    allow_reuse_address = True
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 5

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        """Constructor.  May be extended, do not override."""
        SocketServer.BaseServer.__init__(self, server_address, RequestHandlerClass)
        self.socket = socket.socket(self.address_family, self.socket_type)
        self.__is_shut_down = threading.Event()
        self.__serving = False
        if bind_and_activate:
            self.server_bind()
            self.server_activate()

    def server_bind(self):
        """Called by constructor to bind the socket.

        May be overridden.

        """
        if self.allow_reuse_address:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()

    def server_activate(self):
        """Called by constructor to activate the server.

        May be overridden.

        """
        self.socket.listen(self.request_queue_size)

    def serve_forever(self, poll_interval=0.5):
        """Handle one request at a time until shutdown.

        Polls for shutdown every poll_interval seconds. Ignores
        self.timeout. If you need to do periodic tasks, do them in
        another thread.
        """
        self.logger.info(u'listen')
        self.__serving = True
        self.__is_shut_down.clear()
        while self.__serving:
            # XXX: Consider using another file descriptor or
            # connecting to the socket to wake this up instead of
            # polling. Polling reduces our responsiveness to a
            # shutdown request and wastes cpu at all other times.
            r = select.select([self], [], [], poll_interval)[0]
            if r:
                self._handle_request_noblock()
        self.__is_shut_down.set()
        self.logger.info(u'sucessfully shut down')

    def shutdown(self):
        """Stops the serve_forever loop.

        Blocks until the loop has finished. This must be called while
        serve_forever() is running in another thread, or it will
        deadlock.
        """
        self.logger.info(u'shutdown called')
        self.__serving = False
        self.__is_shut_down.wait()

    def _handle_request_noblock(self):
        """Handle one request, without blocking.

        I assume that select.select has returned that the socket is
        readable before this function was called, so there should be
        no risk of blocking in get_request().
        """
        try:
            request, client_address = self.get_request()
        except socket.error:
            return
        if self.verify_request(request, client_address):
            try:
                self.process_request(request, client_address)
            except:
                self.handle_error(request, client_address)
                self.close_request(request)

    def handle_request(self):
        """Handle one request, possibly blocking.

        Respects self.timeout.
        """
        # Support people who used socket.settimeout() to escape
        # handle_request before self.timeout was available.
        timeout = self.socket.gettimeout()
        if timeout is None:
            timeout = self.timeout
        elif self.timeout is not None:
            timeout = min(timeout, self.timeout)
        fd_sets = select.select([self], [], [], timeout)
        if not fd_sets[0]:
            self.handle_timeout()
            return
        self._handle_request_noblock()


class SupySocketServer(callbacks.Plugin):
    """Add the help for "@plugin help SupySocketServer" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        callbacks.Plugin.__init__(self, irc)
        self._server = None
        self._server_thread = None
        self._start_server_in_thread()

    def _start_server_in_thread(self):
        self._server_thread = threading.Thread(target=self._start_server)
        self._server_thread.daemon = True
        self._server_thread.start()

    def _start_server(self):
        host = self.registryValue('host')
        port = self.registryValue('port')
        self._server = SocketServerImpl((host, port), RequestHandler)
        self._server.logger = self.log
        self._server.serve_forever()

    def die(self):
        if self._server:
            self._server.shutdown()
            self._server_thread.join()


    def outFilter(self, irc, msg):
        if msg.inReplyTo:
            if msg.inReplyTo.supysocketserver:
                target_irc, target, notice = msg.inReplyTo.supysocketserver
                self._reply_command(target_irc, target, msg, notice)
                return None
            else:
                return msg
        else:
            return msg

    def _reply_command(self, target_irc, target, msg, notice):
        if notice:
            factory = ircmsgs.notice
        else:
            factory = ircmsgs.privmsg
        reply_msg = factory(target, msg.args[1])
        target_irc.sendMsg(reply_msg)


Class = SupySocketServer


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
