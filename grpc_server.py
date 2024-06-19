import grpc
from concurrent import futures
import time

import balance_pb2
import balance_pb2_grpc

from pymongo import MongoClient
import redis

# Connect to MongoDB
client = MongoClient('mongo', 27017)
db = client['bank']
users = db['users']

# Connect to Redis
r = redis.Redis(host='redis', port=6379)


class BalanceService(balance_pb2_grpc.BalanceServiceServicer):
    def GetBalance(self, request, context):
        user_id = request.user_id

        # Try to get balance from Redis
        balance = r.get(f"user:{user_id}:balance")
        if balance:
            return balance_pb2.BalanceResponse(balance=int(balance))

        # If not in cache, get from MongoDB
        user = users.find_one({"user_id": user_id})
        if user:
            balance = user['balance']
            r.set(f"user:{user_id}:balance", balance)
            return balance_pb2.BalanceResponse(balance=balance)

        return balance_pb2.BalanceResponse(balance=-1)

    def UpdateBalance(self, request, context):
        user_id = request.user_id
        new_balance = request.new_balance

        # Update balance in MongoDB
        result = users.update_one({"user_id": user_id}, {"$set": {"balance": new_balance}}, upsert=True)

        # Update balance in Redis
        r.set(f"user:{user_id}:balance", new_balance)

        return balance_pb2.UpdateBalanceResponse(success=True)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    balance_pb2_grpc.add_BalanceServiceServicer_to_server(BalanceService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("GRPC server started on port 50051")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    serve()
