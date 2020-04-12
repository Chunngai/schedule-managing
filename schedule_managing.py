#!/usr/bin/nv python

import datetime
import argparse
import traceback
import copy
import re
import os

from wechat_file_helper import send


class TimeSlice:
    def __init__(self, start: datetime.datetime = None, duration: datetime.timedelta = None,
                 end: datetime.datetime = None):
        self.start = start
        self.duration = duration
        self.end = end

    def __eq__(self, other):
        return self.start == other.start and self.duration == other.duration and self.end == other.end


class Task:
    def __init__(self, time_slice: TimeSlice = None, name: str = ''):
        self.time_slice = time_slice
        self.name = name


class Schedule:
    def __init__(self, task_list: list = None, date: datetime.date = None, schedule_str: str = ''):
        if task_list:
            self.task_list = task_list
        else:
            self.task_list = []
        self.date = date
        self.schedule_str = schedule_str
        self.path = os.path.join("schedule", f"{self.date.isoformat()}.txt")
        self.saved = False

    def set_path(self):
        self.path = os.path.join("schedule", f"{self.date.isoformat()}.txt")

    def _task_append(self, new_task):
        if not self.task_list:
            # if the task list is empty, appends the new task to the list directly
            self.task_list.append(new_task)
            return
        elif self.task_list[-1].time_slice.end <= new_task.time_slice.start:
            # if the start time of the new task is later than the end time of the last task in the list,
            # appends the new task to the list directly
            self.task_list.append(new_task)
            return
        elif self.task_list[0].time_slice.start >= new_task.time_slice.end:
            # if the end time of the new task is earlier than the start time of the first task in the list,
            # inserts the new task to the head of the list
            self.task_list.insert(0, new_task)
            return
        else:
            # if there is at least one task in the task list whose time slice is the same as that of the new task,
            # appends the new task to the task list and sorts the list
            for i in range(len(self.task_list)):
                if self.task_list[i].time_slice == new_task.time_slice:
                    self.task_list.append(new_task)
                    self.task_list.sort(key=lambda task: task.time_slice.start)
                    return

            for i in range(len(self.task_list) - 1):
                # if there is no task in the task list whose time slice id the same as that of the new task,
                # finds if there is a time slice that is not occupied by the existed tasks.
                # if one is found, appends the new task to the task list and sorts the list
                if self.task_list[i].time_slice.start != self.task_list[i + 1].time_slice.start \
                        and self.task_list[i].time_slice.end <= new_task.time_slice.start \
                        and new_task.time_slice.end <= self.task_list[i + 1].time_slice.start:
                    self.task_list.append(new_task)
                    self.task_list.sort(key=lambda task: task.time_slice.start)
                    return

        print(f"{err_msg}time slice conflict")
        raise Exception

    @staticmethod
    def _duration_end_validation(start, duration, end):
        if not duration and not end:
            print(f"{err_msg}one of the arguments --duration/-d --end/-e is required")
            raise Exception

        if duration:
            end = start + duration
        elif end:
            if start > end:
                print(f"{err_msg}start time should be earlier than end time")
                raise Exception

            duration = end - start

        return duration, end

    def _add_validation(self, start, duration, end, task_name):
        if not task_name:
            print(f"{err_msg}the following arguments are required: --task_name/-t")

        if self.task_list:
            last_task_time_slice = self.task_list[-1].time_slice
            # start, duration and end can be omitted if the task list is not empty
            # in this condition the start, duration and end of the last task in the task list will be used
            if not (start or duration or end):
                start = last_task_time_slice.start
                duration = last_task_time_slice.duration
                end = last_task_time_slice.end
            # if start is not specified and duration or end is specified, end of the last task will be used
            if not start and (duration or end):
                start = last_task_time_slice.end

        if not start:
            print(f"{err_msg}the following arguments are required: --start/-s")
            raise Exception
        duration, end = self._duration_end_validation(start, duration, end)

        return start, duration, end, task_name

    @staticmethod
    def _strf(duration):
        hours, minutes = divmod(duration.seconds, 3600)
        minutes, seconds = divmod(minutes, 60)

        return f"{str(hours).zfill(2)}h {str(minutes).zfill(2)}min"

    def _schedule_format(self):
        self.schedule_str = ''

        for i in range(len(self.task_list)):
            time_slice = self.task_list[i].time_slice
            name = self.task_list[i].name
            if i > 0 \
                    and time_slice.start == self.task_list[i - 1].time_slice.start \
                    and time_slice.end == self.task_list[i - 1].time_slice.end:
                self.schedule_str += f"({i}) {' '.ljust(26 - len(str(i)) - 2)}{name}\n"
            else:
                start = time_slice.start.strftime("%H:%M")
                duration = Schedule._strf(time_slice.duration)
                end = time_slice.end.strftime("%H:%M")

                self.schedule_str += f"({i}) {start}-{end} {duration}: {name}\n"

    def add_a_task(self, start, duration, end, task_name, rest_duration):
        start, duration, end, task_name = self._add_validation(start, duration, end, task_name)

        # creates a task
        task = Task()
        task.time_slice = TimeSlice(start, duration, end)
        task.name = task_name

        # appends the task to the task list
        self._task_append(task)

        # creates a task for taking a rest if -r [REST-DURATION] is provided
        if rest_duration:
            # creates a task
            rest = Task()
            rest.time_slice = TimeSlice(end, rest_duration[0], end + rest_duration[0])
            rest.name = "take a rest"

            # appends the task to the task list
            self._task_append(rest)

        self.display_schedule()
        self.saved = False

    def modify_a_task(self, task_index, start, duration, end, task_name):
        # start or task name should be provided
        if not start and not task_name:
            print(f"{err_msg}one of the arguments --start/- --task-name/-t is required")
            raise Exception

        # modifies the task name
        if task_name:
            self.task_list[task_index].name = task_name

        # modifies the time slice
        if start:
            # modifies the task time slice
            time_slice = self.task_list[task_index].time_slice
            time_slice_copy = copy.deepcopy(time_slice)  # deep copy

            time_slice_copy.start = start
            time_slice_copy.duration, time_slice_copy.end = self._duration_end_validation(start, duration, end)

            # start time of the task should be later than that of its preceding task
            if 0 < task_index and self.task_list[task_index - 1].time_slice.end > time_slice_copy.start:
                print(f"{err_msg}time slice conflict")
                raise Exception

            time_delta = time_slice_copy.start - time_slice.start

            time_slice.start, time_slice.duration, time_slice.end = \
                time_slice_copy.start, time_slice_copy.duration, time_slice_copy.end

            # modifies the time slice of tasks after the current task
            for i in range(task_index + 1, len(self.task_list)):
                time_slice = self.task_list[i].time_slice

                time_slice.start += time_delta
                time_slice.end += time_delta

        self.display_schedule()
        self.saved = False

    def delete_a_task(self, task_index):
        self.task_list.pop(task_index)
        self.display_schedule()
        self.saved = False

    def save_to_txt(self):
        if not self.task_list:
            print("nothing saved. the task list is empty")
            return

        try:
            with open(self.path) as f:
                content = f.read()
        except FileNotFoundError:
            pass
        else:
            print(f"content in {os.path.basename(self.path)}:")
            print(content)
            input_ = input("override? (y/n)\n")
            if input_ == 'y':
                pass
            elif input_ == 'n':
                self.path = os.path.join("schedule", f"{self.date.isoformat()}_(copy).txt")
            else:
                print(f"{err_msg}valid input: y, n")
                return

        self._schedule_format()
        with open(self.path, 'w') as f:
            f.write(self.schedule_str)

        self.saved = True

    def send_to_wechat(self):
        self._schedule_format()
        send([self.schedule_str])

    def display_schedule(self):
        self._schedule_format()
        print(self.schedule_str)


def make_dir():
    try:
        os.mkdir("schedule")
    except FileExistsError:
        pass


def read_from_txt(schedule_date):
    # saves the current schedule
    global schedule
    if schedule.task_list:
        schedule.save_to_txt()

    try:
        with open(os.path.join("schedule", f"{schedule_date}.txt"), 'r') as f:
            schedule_str = f.read()
    except FileNotFoundError:
        print(f"{err_msg}{schedule_date}.txt not exists")
        raise Exception
    else:
        schedule_date_list = schedule_date.split('-')
        year = int(schedule_date_list[0])
        month = int(schedule_date_list[1])
        day = int(schedule_date_list[2])

        # creates a new schedule obj to receives the schedule being read
        schedule = Schedule(date=datetime.date(year=year, month=month, day=day))

        task_str_list = schedule_str.split('\n')

        pat1 = re.compile(r"\((\d+?)\) (\d\d:\d\d)-(\d\d:\d\d) (\d+?)h (\d+?)min: (.+)")
        pat2 = re.compile(r"\((\d+?)\)\s+(.+)")
        for task_str in task_str_list:
            rst1 = pat1.search(task_str)
            rst2 = pat2.search(task_str)

            if rst1:
                start_str = rst1.group(2)
                start_h = int(start_str.split(':')[0])
                start_min = int(start_str.split(':')[1])
                start = datetime.datetime(year=year, month=month, day=day, hour=start_h, minute=start_min)

                end_str = rst1.group(3)
                end_h = int(end_str.split(':')[0])
                end_min = int(end_str.split(':')[1])
                end = datetime.datetime(year=year, month=month, day=day, hour=end_h, minute=end_min)

                duration = end - start

                time_slice = TimeSlice(start, duration, end)
                task_name = rst1.group(6)
                task = Task(time_slice, task_name)

                schedule.task_list.append(task)
            elif rst2:
                time_slice = copy.deepcopy(schedule.task_list[-1].time_slice)
                task_name = rst2.group(2)
                task = Task(time_slice, task_name)

                schedule.task_list.append(task)

        schedule.display_schedule()
        schedule.saved = True


def schedule_managing(parser):
    make_dir()

    while True:
        input_ = input()

        try:
            args = parser.parse_args(input_.split())

            if args.read:
                read_from_txt(args.read[0])
            if args.save:
                schedule.save_to_txt()
            if args.send:
                schedule.send_to_wechat()
            if args.display:
                schedule.display_schedule()
            if args.quit:
                if schedule.saved is False:
                    input_ = input(f"{os.path.basename(schedule.path)} "
                                   "is updated but not saved. save now? (y/n)\n")
                    if input_ == 'y':
                        schedule.save_to_txt()
                        break
                    elif input_ == 'n':
                        break
                    else:
                        print(f"{err_msg}valid input: y, n")
                else:
                    break

            if not any([args.read, args.save, args.send, args.display,
                        args.quit]):
                args.func(args)
        except:
            # print(traceback.format_exc())
            pass


class ScheduleManagingArgTypeCheck:
    def __init__(self):
        pass

    @classmethod
    def check_time(cls, time_input):
        if len(str(time_input)) != 4:
            raise argparse.ArgumentTypeError("input format: HHMM (len of the arg is 4)")

        try:
            time = int(time_input)  # raises ValueError if the the input is not int

            hh, mm = divmod(time, 100)
            # raises ValueError if HH and MM does not satisfy the requirement of datetime.datetime()
            time = datetime.datetime(year=schedule.date.year, month=schedule.date.month, day=schedule.date.day,
                                     hour=hh, minute=mm)

            return time
        except ValueError:
            raise argparse.ArgumentTypeError("input format: HHMM. 0 <= HH <= 23, 0 <= MM <= 59")

    @classmethod
    def _check_delta(cls, delta_input):
        try:
            delta = [int(duration) for duration in delta_input.split('h')]  # raises ValueError if the format is wrong
        except ValueError:
            raise argparse.ArgumentTypeError("input format: HHhMM such as 1h30, or MM such as 90")
        else:
            if len(delta) == 1:
                return datetime.timedelta(minutes=delta[0])
            else:
                return datetime.timedelta(hours=delta[0], minutes=delta[1])

    @classmethod
    def check_duration(cls, duration_input):
        duration = ScheduleManagingArgTypeCheck._check_delta(duration_input)

        if duration.days >= 0:
            return duration
        else:
            raise argparse.ArgumentTypeError("duration should be greater than 0")

    @classmethod
    def check_index(cls, index_input):
        try:
            index = int(index_input)  # raises ValueError if the index input is not int

            if not (0 <= index < len(schedule.task_list)):  # if the condition is true, the index input is out of range
                raise IndexError

            return index
        except ValueError:
            raise argparse.ArgumentTypeError("index should be an int")
        except IndexError:
            raise argparse.ArgumentTypeError("index should be in [0, TASK_LIST_LEN - 1]")

    @classmethod
    def check_date(cls, date_input):
        pat = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        if not pat.search(date_input):
            raise argparse.ArgumentTypeError("invalid date format. valid format: YYYY-MM-DD")
        return date_input


class ReadAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super(ReadAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_strings=None):
        if len(values) > 1:
            print(f"{err_msg}expected one or no argument")
            raise Exception
        elif not len(values):
            # -R
            values = [schedule.date.strftime("%Y-%m-%d")]
            setattr(namespace, self.dest, values)
        else:
            # -R date: YYYY-MM-DD
            setattr(namespace, self.dest, values)


class TaskAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super(TaskAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_strings=None):
        values = ' '.join(values)
        setattr(namespace, self.dest, values)


class RestTimeAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super(RestTimeAction, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        if len(values) > 1:
            print(f"{err_msg}expected one or no argument")
            raise Exception
        elif not len(values):
            # -r
            values = [datetime.timedelta(minutes=10)]
            setattr(namespace, self.dest, values)
        else:
            # -r rest-duration: int
            setattr(namespace, self.dest, values)


if __name__ == '__main__':
    schedule_day = datetime.date.today() + datetime.timedelta(days=1)
    schedule = Schedule(date=schedule_day)

    err_msg = "schedule_managing.py: error: "

    parser = argparse.ArgumentParser(description="schedule-managing.py - a tool for creating and managing schedules")
    parser.add_argument("--run", "-r",
                        action="store_true",
                        help="run the program")
    parser.add_argument("--quit", "-q",
                        action="store_true",
                        help="exit the program")
    parser.add_argument("--today", "-t",
                        action="store_true",
                        help="create a schedule for today (for tomorrow by default)")
    parser.add_argument("--save", "-s",
                        action="store_true",
                        help="save the schedule in a txt")
    parser.add_argument("--read", "-R",
                        action=ReadAction,
                        nargs='*',
                        type=ScheduleManagingArgTypeCheck.check_date,
                        help="read the schedule from its txt")
    parser.add_argument("--send", "-S",
                        action="store_true",
                        help="send the schedule to wechat file helper")
    parser.add_argument("--display", "-p",
                        action="store_true",
                        help="displays the schedule")

    subparsers = parser.add_subparsers()

    # parser for adding a task
    add_a_task_parser = subparsers.add_parser(name="add-a-task",
                                              aliases=["a"],
                                              conflict_handler='resolve',
                                              description="add a task to the schedule")
    add_a_task_parser.add_argument("--start", "-s",
                                   action="store",
                                   type=ScheduleManagingArgTypeCheck.check_time,
                                   help="start of the time slice")
    add_a_task_exclusive_group = add_a_task_parser.add_mutually_exclusive_group()
    add_a_task_exclusive_group.add_argument("--duration", "-d",
                                            action="store",
                                            type=ScheduleManagingArgTypeCheck.check_duration,
                                            help="duration of the time slice")
    add_a_task_exclusive_group.add_argument("--end", "-e",
                                            action="store",
                                            type=ScheduleManagingArgTypeCheck.check_time,
                                            help="end of the time slice")
    add_a_task_parser.add_argument("--task_name", "-t",
                                   action=TaskAction,
                                   nargs="+",
                                   required=True,
                                   help="name of the task")
    add_a_task_parser.add_argument("--rest-duration", "-r",
                                   action=RestTimeAction,
                                   nargs='*',
                                   type=ScheduleManagingArgTypeCheck.check_duration,
                                   help="duration of a rest, 10 minutes by default")
    add_a_task_parser.set_defaults(func=lambda args: schedule.add_a_task(
        args.start, args.duration, args.end, args.task_name, args.rest_duration))

    # parser for modifying a task
    modify_a_task_parser = subparsers.add_parser("modify",
                                                 aliases=["m"],
                                                 conflict_handler='resolve')
    modify_a_task_parser.add_argument("--task-index", "-i",
                                      action="store",
                                      type=ScheduleManagingArgTypeCheck.check_index,
                                      required=True,
                                      help="index of task to be modified")
    modify_a_task_parser.add_argument("--start", "-s",
                                      action="store",
                                      type=ScheduleManagingArgTypeCheck.check_time,
                                      help="start of the time slice")
    modify_a_task_exclusive_group = modify_a_task_parser.add_mutually_exclusive_group()
    modify_a_task_exclusive_group.add_argument("--duration", "-d",
                                               action="store",
                                               type=ScheduleManagingArgTypeCheck.check_duration,
                                               help="duration of the time slice")
    modify_a_task_exclusive_group.add_argument("--end", "-e",
                                               action="store",
                                               type=ScheduleManagingArgTypeCheck.check_time,
                                               help="end of the time slice")
    modify_a_task_parser.add_argument("--task_name", "-t",
                                      action=TaskAction,
                                      nargs='+',
                                      help="name of the task")
    modify_a_task_parser.set_defaults(func=lambda args: schedule.modify_a_task(
        args.task_index, args.start, args.duration, args.end, args.task_name))

    # parser for deleting a task
    delete_a_task_parser = subparsers.add_parser("delete",
                                                 aliases=["d"])
    delete_a_task_parser.add_argument("--task-index", "-i",
                                      action="store",
                                      type=ScheduleManagingArgTypeCheck.check_index,
                                      required=True,
                                      help="index of task to be deleted")
    delete_a_task_parser.set_defaults(func=lambda args: schedule.delete_a_task(args.task_index))

    args = parser.parse_args()

    if args.run:
        if args.today:
            schedule.date -= datetime.timedelta(days=1)
            schedule.set_path()
        schedule_managing(parser)
