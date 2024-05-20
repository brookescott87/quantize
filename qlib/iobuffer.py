class IOBuffer(object):
    def __init__(self, capacity):
        self.capacity = capacity
        self.buffer = bytearray(capacity)
        self.length = 0

    @property
    def bytes(self):
        if self.length < self.capacity:
            return self.buffer[0:self.length]
        else:
            return self.buffer

    def readfrom(self, f):
        self.length = f.readinto(self.buffer)
        return self.length
    
    def writeto(self, f):
        return f.write(self.bytes) if self.length else 0

