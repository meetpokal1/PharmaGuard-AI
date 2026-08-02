import random
from datetime import datetime


def generate_complaint_id():

    date = datetime.now().strftime("%Y%m%d")

    number = random.randint(1000, 9999)

    return f"CMP-{date}-{number}"
