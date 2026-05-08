import itertools

import dateutil.utils

from main.models import *


from collections import defaultdict

adjacency = defaultdict(set)
# id would be more efficient than slug but we're using slug for visability for now
pairs = (
    Fight_Version.objects
    .select_related("version__robot", "fight")
    .values_list("fight_id", "version__robot__slug")
)

fight_to_robots = defaultdict(set)

for fight_id, robot_slug in pairs:
    fight_to_robots[fight_id].add(robot_slug)

for robots in fight_to_robots.values():
    for r1 in robots:
        adjacency[r1].update(robots - {r1})

robot_data = {}

robot_contest_pairs = (
    Robot.objects
    .values_list(
        "slug",
        "version__fight_version__fight__contest_id"
    )
    .distinct()
)

robot_to_events = defaultdict(set)

for robot_id, event_id in robot_contest_pairs:
    robot_to_events[robot_id].add(event_id)

robot_wc_pairs = (
    Robot.objects
    .values_list(
        "slug",
        "version__weight_class_id"
    )
    .distinct()
)
lb_classes = {}
for wc in Weight_Class.objects.all():
    lb_classes[wc.id] = wc.find_lb_class()

robot_to_wc = defaultdict(set)
for robot_id, wc in robot_wc_pairs:
    robot_to_wc[robot_id].add(lb_classes[wc])

ordered_weights = {"F": 0, "L": 1, "M": 2, "H": 3, "S": 4}

for robot in Robot.objects.all():
    weights = robot_to_wc[robot.slug].copy()
    to_remove = set()
    for w in weights:
        if w not in ordered_weights:
            to_remove.add(w)
    weights -= to_remove
    robot_data[robot.slug] = {
        "country": robot.country,
        "first_year": robot.first_fought.year if robot.first_fought else 1994,
        "last_year": robot.last_fought.year if robot.last_fought else dateutil.utils.today().year,
        "weights": weights,
        "contests": robot_to_events[robot.slug].copy(),
        "adjacency": adjacency[robot.slug].copy()
    }

#print(robot_data["razer"])

country_graph = defaultdict(int)
outgoing_connections = defaultdict(int)
for robot, info in robot_data.items():
    for robot_b in info["adjacency"]:
        ca = info["country"]
        cb = robot_data[robot_b]["country"]
        if ca != cb:
            country_graph[(ca, cb)] += 1
            outgoing_connections[ca] += 1

country_affinity = {}

for (ca, cb), count in country_graph.items():
    country_affinity[(ca, cb)] = count / outgoing_connections[ca]


def distance(slug_a, slug_b):
    a = robot_data[slug_a]
    b = robot_data[slug_b]

    country_distance = 0
    if a["country"] != b["country"]:
        country_pair = (a["country"], b["country"])
        if country_pair in country_affinity:
            country_distance = 10 - 10 * country_affinity[country_pair]
        else:
            country_distance = 10

    weight_distance = 0
    if len(a["weights"]) == 0 or len(b["weights"]) == 0:
        weight_distance = 10
    elif not any(w in b["weights"] for w in a["weights"]):
        weight_distance = 10 * min(
            abs(ordered_weights[i] - ordered_weights[j]) / (len(ordered_weights) - 1) for i, j in
            list(itertools.product(a["weights"], b["weights"])))

    year_distance: int
    if a["first_year"] == b["first_year"] and a["last_year"] == b["last_year"]:
        year_distance = 0
    elif (b["first_year"] <= a["first_year"] <= b["last_year"]) or (
            b["first_year"] <= a["last_year"] <= b["last_year"]) or (
            a["first_year"] <= b["first_year"] <= a["last_year"]):
        fought_range = max(a["last_year"], b["last_year"]) - min(a["first_year"], b["first_year"])
        overlap_range = min(a["last_year"], b["last_year"]) - max(a["first_year"], b["first_year"])
        year_distance = 2 + (8 - 8 * overlap_range / fought_range)
    else:
        year_distance = 10

    contest_distance = 20
    if any(x == y for x, y in itertools.product(a["contests"], b["contests"])):
        contest_distance = 0
    #print(slug_a + " -> " + slug_b)
    #print(country_distance + weight_distance + year_distance + contest_distance, "|", country_distance, weight_distance,
    #      year_distance, contest_distance)
    return country_distance + weight_distance + year_distance + contest_distance


class Node:
    distance_factor = 50 / 6
    heuristic = 0
    item = None
    previous = None
    prio = 0

    def __init__(self, thumb, item, previous):
        self.heuristic = thumb
        self.item = item
        self.previous = previous
        self.prio = self.heuristic + len(self)*Node.distance_factor

    def __eq__(self, other):
        if other is Node:
            if self.item != other.item:
                return False
            elif self.previous is None and other.previous is None:
                return True
            else:
                return self.previous == other.previous
        else:
            return other == self.item

    def __gt__(self, other):
        if other is Node:
            return self.prio > other.prio
        else:
            return self.prio > other

    def __lt__(self, other):
        if other is Node:
            return self.prio < other.prio
        else:
            return self.prio < other

    def __ge__(self, other):
        if other is Node:
            return self.prio >= other.prio
        else:
            return self.prio >= other

    def __le__(self, other):
        if other is Node:
            return self.prio <= other.prio
        else:
            return self.prio <= other

    def __str__(self):
        if self.previous is None:
            return str((self.prio, self.item, None))
        else:
            return str((self.prio, self.item, self.previous.item))

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        num = 0
        check = self
        while check is not None:
            check = check.previous
            num += 1
        return num


class pq:
    nodes = []
    min = 5 * 10 ** 10
    max = -5 * 10 ** 10

    def __init__(self, node=None):
        if node:
            self.nodes = [node]

    def push(self, node):
        if node in self.nodes:
            return
        if node >= self.max:
            self.max = node.prio
            self.nodes.append(node)
        elif node <= self.min:
            self.min = node.prio
            self.nodes = [node] + self.nodes
        else:
            for i in range(len(self.nodes)):
                if node.prio < self.nodes[i].prio:
                    self.nodes = self.nodes[:i] + [node] + self.nodes[i:]
                    break

    def pop(self):
        return self.nodes.pop(0)

    def __len__(self):
        return len(self.nodes)

    def __str__(self):
        return str(self.nodes)


def six_degrees(slug1, slug2):
    node = Node(0, slug1, None)
    thequeue = pq(node)
    searched = [node]
    while len(thequeue) > 0:
        node = thequeue.pop()
        if node.item == slug2:
            break
        data = robot_data[node.item]
        for s in data["adjacency"]:
            if s in searched:
                continue
            new = Node(distance(s, slug2), s, node)
            #print("Testing",new)
            if new in [n.item for n in thequeue.nodes]:
                old_node = thequeue.nodes.pop(thequeue.nodes.index(new))
                if new <= old_node:
                    thequeue.push(new)
                else:
                    thequeue.push(old_node)
            else:
                thequeue.push(new)
            searched.append(new)
        #print(thequeue)
    print(thequeue)
    while node is not None:
        print(node)
        node = node.previous


def six_degrees_old(slug1, slug2):
    start_rob = Robot.objects.get(slug=slug1)
    end_rob = Robot.objects.get(slug=slug2)
    searched = {start_rob}
    thequeue = pq()

    def makequeue(test_node: Node):
        test_rob: Robot
        test_rob = test_node.item
        opponents = set()
        for fight in Fight.objects.filter(fight_version__version__robot=test_rob).distinct():
            robots_from_fight = Robot.objects.filter(version__fight_version__fight=fight).distinct().exclude(
                slug=test_rob.slug)
            opponents = opponents.union(list(robots_from_fight))
            new = opponents.difference(searched)
            if end_rob in new:
                thequeue.push(Node(5 * 10 ** 11, end_rob, test_node))
                return

        new_robot: Robot
        for new_robot in new:
            num = 0
            new_rob_weight = Weight_Class.objects.get(
                id=new_robot.version_set.all().values("weight_class_id").annotate(count=Count('weight_class_id'))[0][
                    'weight_class_id']).weight_grams
            end_rob_weight = Weight_Class.objects.get(
                id=end_rob.version_set.all().values("weight_class_id").annotate(count=Count('weight_class_id'))[0][
                    'weight_class_id']).weight_grams
            if new_rob_weight == end_rob_weight:
                num += 10
            elif new_rob_weight != 0:
                num += ((5.5 - abs(log(new_rob_weight) - log(end_rob_weight))) / 5.5) * 8
            if new_robot.country == end_rob.country:
                num += 10
            if new_robot.first_fought.year == end_rob.first_fought.year and new_robot.last_fought.year == end_rob.last_fought.year:
                num += 10
            elif new_robot.first_fought.year == end_rob.first_fought.year or new_robot.last_fought.year == end_rob.last_fought.year:
                num += 7
            elif new_robot.first_fought.year <= end_rob.last_fought.year and end_rob.first_fought.year <= new_robot.last_fought.year:
                num += 5
            if Event.objects.filter(contest__fight__fight_version__version__robot=new_robot).union(
                    Event.objects.filter(contest__fight__fight_version__version__robot=end_rob)).count() > 1:
                num += 20
            num -= len(test_node) * 7.5
            thequeue.push(Node(num, new_robot, test_node))
            searched.add(new_robot)
        print(thequeue)

    thequeue.push(Node(0, start_rob, None))
    test = None
    while len(thequeue) != 0:
        test = thequeue.pop()
        if test.item == end_rob:
            break
        else:
            makequeue(test)
    while test is not None:
        print(str(test.item) + " > ", end="")
        test = test.previous
    print()
