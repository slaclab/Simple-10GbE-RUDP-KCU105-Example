#-----------------------------------------------------------------------------
# This file is part of the 'Simple-10GbE-RUDP-KCU105-Example'. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the 'Simple-10GbE-RUDP-KCU105-Example', including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import rogue.interfaces.stream as ris
import pyrogue as pr
import numpy as np

#################################################################

class FrameStrut(object):
    def __init__(self):
        #############################
        # Header
        #############################
        self.header = None
        #############################
        # Payload
        #############################
        self.wrdData = None

#################################################################

def ParseFrame(frame):
    # Next we can get the size of the frame payload
    size = frame.getPayload()

    # To access the data we need to create a byte array to hold the data
    fullData = bytearray(size)

    # Next we read the frame data into the byte array, from offset 0
    frame.read(fullData,0)

    # Calculate the number of pixel words
    num64bWords = (size>>3)

    # Create the event
    eventFrame = FrameStrut()

    # Fill an array of 64-bit formatted word
    eventFrame.wrdData = [None for i in range(num64bWords)]
    eventFrame.wrdData = np.frombuffer(fullData, dtype='uint64', count=num64bWords)

    # Parse the data header
    eventFrame.header = eventFrame.wrdData[0]

    # Return the results
    return eventFrame

#################################################################
# Refer to the following:
# https://slaclab.github.io/rogue/interfaces/stream/receiving.html
# https://github.com/slaclab/rogue/blob/master/python/pyrogue/_DataReceiver.py
#################################################################

# Class for streaming RX
class SwRx(pr.DataReceiver):
    # Init method must call the parent class init
    def __init__( self,**kwargs):
        super().__init__(**kwargs)

        self.add(pr.LocalVariable(
            name        = 'DebugPrint',
            description = 'Flag to enable debug printing',
            value       = False,
        ))

    # Method which is called when a frame is received
    def process(self,frame):

        # Print out the event
        if self.DebugPrint.get():
            # Parse the frame
            eventFrame = ParseFrame(frame)

            # Print the header
            print( f'eventFrame.header = {eventFrame.header}' )

#################################################################
