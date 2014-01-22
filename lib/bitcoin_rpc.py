'''
    Implements simple interface to a coin daemon's RPC.
'''

import simplejson as json
import base64
from twisted.internet import defer
from twisted.web import client
import time

import lib.logger
log = lib.logger.get_logger('bitcoin_rpc')

class BitcoinRPC(object):
    
    def __init__(self, host, port, username, password):
	log.debug("Got to Bitcoin RPC")
        self.bitcoin_url = 'http://%s:%d' % (host, port)
        self.credentials = base64.b64encode("%s:%s" % (username, password))
        self.headers = {
            'Content-Type': 'text/json',
            'Authorization': 'Basic %s' % self.credentials,
        }
        self.has_submitblock = None
	client.HTTPClientFactory.noisy = False
        
    def _call_raw(self, data):
        client.Headers
        return client.getPage(
            url=self.bitcoin_url,
            method='POST',
            headers=self.headers,
            postdata=data,
        )
           
    def _call(self, method, params):
        return self._call_raw(json.dumps({
                'jsonrpc': '2.0',
                'method': method,
                'params': params,
                'id': '1',
            }))

    @defer.inlineCallbacks
    def check_submitblock(self):
        try:
            log.debug("Checking for submitblock")
            resp = (yield self._call('submitblock', []))
            log.debug("unknown submitblock check result.")
            self.has_submitblock = None

        except Exception as e:
            if (str(e) == "404 Not Found"):
                log.debug("No submitblock detected.")
                self.has_submitblock = False
            elif (str(e) == "500 Internal Server Error"):
                log.debug("submitblock detected.")
                self.has_submitblock = True
            else:
                log.debug("unknown submitblock check result.")
                self.has_submitblock = True
        finally:
            defer.returnValue(self.has_submitblock)

    @defer.inlineCallbacks
    def submitblock(self, block_hex, hash_hex):
    #try 5 times? 500 Internal Server Error could mean random error or that TX messages setting is wrong
        attempts = 0
        while True:
            attempts += 1
            if self.has_submitblock == True:
                try:
                    log.debug("Submitting Block with submitblock: attempt #"+str(attempts))
                    log.debug([block_hex,])
                    resp = (yield self._call('submitblock', [block_hex,]))
                    log.debug("SUBMITBLOCK RESULT: %s", resp)
                    break
                except Exception as e:
                    if attempts > 4:
                        log.exception("submitblock failed. Problem Submitting block %s" % str(e))
                        log.exception("Try Enabling TX Messages in config.py!")
                        raise
                    else:
                        continue
            elif self.has_submitblock == False:
                try:
                    log.debug("Submitting Block with getblocktemplate submit: attempt #"+str(attempts))
                    log.debug([block_hex,])
                    resp = (yield self._call('getblocktemplate', [{'mode': 'submit', 'data': block_hex}]))
                    break
                except Exception as e:
                    if attempts > 4:
                        log.exception("getblocktemplate submit failed. Problem Submitting block %s" % str(e))
                        log.exception("Try Enabling TX Messages in config.py!")
                        raise
                    else:
                        continue
            else:  # self.has_submitblock = None; unable to detect submitblock, try both
                try:
                    log.debug("Submitting Block with submitblock")
                    log.debug([block_hex,])
                    resp = (yield self._call('submitblock', [block_hex,]))
                    break
                except Exception as e:
                    try:
                        log.exception("submitblock Failed, does the coind have submitblock?")
                        log.exception("Trying GetBlockTemplate")
                        resp = (yield self._call('getblocktemplate', [{'mode': 'submit', 'data': block_hex}]))
                        break
                    except Exception as e:
                        if attempts > 4:
                            log.exception("submitblock failed. Problem Submitting block %s" % str(e))
                            log.exception("Try Enabling TX Messages in config.py!")
                            raise
                        else:
                            continue

        if json.loads(resp)['result'] == None:
            # make sure the block was created.
            log.info("CHECKING FOR BLOCK AFTER SUBMITBLOCK")
            defer.returnValue((yield self.blockexists(hash_hex, block_hex)))
        else:
            defer.returnValue(False)

    @defer.inlineCallbacks
    def getinfo(self):
         resp = (yield self._call('getinfo', []))
         defer.returnValue(json.loads(resp)['result'])
    
    @defer.inlineCallbacks
    def getblocktemplate(self):
        resp = (yield self._call('getblocktemplate', [{}]))
        defer.returnValue(json.loads(resp)['result'])
                                                  
    @defer.inlineCallbacks
    def prevhash(self):
        resp = (yield self._call('getwork', []))
        try:
            defer.returnValue(json.loads(resp)['result']['data'][8:72])
        except Exception as e:
            log.exception("Cannot decode prevhash %s" % str(e))
            raise
        
    @defer.inlineCallbacks
    def validateaddress(self, address):
        resp = (yield self._call('validateaddress', [address,]))
	defer.returnValue(json.loads(resp)['result'])
	
    @defer.inlineCallbacks
    def getdifficulty(self):
        resp = (yield self._call('getdifficulty', []))
        defer.returnValue(json.loads(resp)['result'])

    @defer.inlineCallbacks
    def blockexists(self, hash_hex, block_hex):
        # try both hash_hex and block_hex to find block
        try:
            resp = (yield self._call('getblock', [hash_hex,]))
            if "hash" in json.loads(resp)['result'] and json.loads(resp)['result']['hash'] == hash_hex:
                log.debug("Block Confirmed: %s" % hash_hex)
                defer.returnValue(True)
            else:
                log.info("Cannot find block for %s" % hash_hex)
                defer.returnValue(False)

        except Exception as e:
            try:
                resp = (yield self._call('getblock', [block_hex,]))
                if "hash" in json.loads(resp)['result'] and json.loads(resp)['result']['hash'] == block_hex:
                    log.debug("Block Confirmed: %s" % block_hex)
                    defer.returnValue(True)
                else:
                    log.info("Cannot find block for %s" % block_hex)
                    defer.returnValue(False)

            except Exception as e:
                log.info("Cannot find block for hash_hex %s or block_hex %s" % hash_hex, block_hex)
                defer.returnValue(False)



