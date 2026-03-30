from multiprocessing import Queue


class Board:
    def __init__(self,board_q:Queue):
        self.board_q = board_q
    @classmethod
    async def create(cls,board_q:Queue):
        self = cls(board_q)

        return self
    def encodeRGB(self,red:int,green:int,blue:int):
        red_byte=red.to_bytes(1,byteorder="big")
        green_byte=green.to_bytes(1,byteorder="big")
        blue_byte=blue.to_bytes(1,byteorder="big")
        byte_combined=red_byte+green_byte+blue_byte
        self.board_q.put(byte_combined)
    async def isModuleActive(self):
        return True
