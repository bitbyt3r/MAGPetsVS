from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from autobahn import wamp
import logging
import redis
import sys
import os

logger = logging.getLogger(__name__)
logger.setLevel(10)

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    db=int(os.environ.get("REDIS_DB", "0")),
    decode_responses=True,
)

class Cat():
    def __init__(self, id, name, image, score):
        self.id = id
        self.name = name
        self.image = image
        self.score = score
        self.health = 100
        self.statuses = []

    def dump(self):
        return {
            "id": self.id,
            "name": self.name,
            "image": self.image,
            "score": self.score,
            "health": self.health,
            "statuses": self.statuses
        }

class GameServer(ApplicationSession):
    def __init__(self, *args, **kwargs):
        ApplicationSession.__init__(self, *args, **kwargs)
        self.cats = []
        self.next_cats = []
        self.loaded_images = []

    async def onJoin(self, details):
        logger.debug("Joined successfully")
        results = await self.subscribe(self)
        for res in results:
            if isinstance(res, wamp.protocol.Subscription):
                logger.info(f"Ok, subscribed handler with subscription ID {res.id}")
            else:
                logger.error(f"Failed to subscribe handler: {res}")
        results = await self.register(self)
        for res in results:
            if isinstance(res, wamp.protocol.Registration):
                logger.info(f"Ok, registered procedure with registration ID {res.id}")
            else:
                logger.error(f"Failed to register handler: {res}")
        cats = r.hrandfield("names", count=2)
        if len(cats) < 2:
            logger.error(f"At least two cats must be loaded to start the game.")
            sys.exit()
        names = r.hmget("names", *cats)
        images = r.hmget("urls", *cats)
        scores = r.zmscore("scores", cats)
        self.cats = [Cat(*x) for x in zip(cats, names, images, scores)]
        self.next_cats = r.hrandfield("names", count=2)
        image_urls = list(images)
        image_urls.extend(r.hmget("urls", *self.next_cats))
        self.loaded_images = dict(zip(cats+self.next_cats, image_urls))
        self.publish('com.gamestart', self.cats[0].dump(), self.cats[1].dump(), self.loaded_images)

    async def onClose(self, details):
        logger.error("Connection closed")

    @wamp.register('com.getstate')
    def getstate(self):
        logger.info("Getstate")
        return self.cats[0].dump(), self.cats[1].dump(), self.loaded_images
        
    @wamp.register('com.attack')
    def vote(self, choice):
        logger.info(f"Attacked {choice}")
        if not choice in self.votes:
            self.votes[choice] = 0
        self.votes[choice] += 1
        self.publish("com.attacks", choice)
        return self.votes[choice]

if __name__ == '__main__':
    url = os.environ.get("AUTOBAHN_ROUTER", "ws://127.0.0.1:8080/ws")
    realm = "MAGPetsVS"
    runner = ApplicationRunner(url, realm)
    runner.run(GameServer)
