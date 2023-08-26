from rq_scheduler import Scheduler

from utils.redis import low_prio_queue

tasks_scheduler = Scheduler(queue=low_prio_queue, connection=low_prio_queue.connection)
