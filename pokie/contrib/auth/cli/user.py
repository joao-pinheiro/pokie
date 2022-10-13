from argparse import ArgumentParser
import getpass
from rick.form import RequestRecord, field

from pokie.contrib.auth.constants import SVC_USER, SVC_AUTH
from pokie.constants import DI_SERVICE_MANAGER
from pokie.contrib.auth.dto import UserRecord
from pokie.contrib.auth.service import UserService, AuthService
from pokie.core import CliCommand


class UserCreateRequest(RequestRecord):
    fields = {
        'username': field(validators="required|minlen:1|maxlen:200", error="invalid username"),
        'email': field(validators="required|minlen:3|maxlen:200|email", error="invalid email address"),
        'first_name': field(validators="maxlen:100", error="invalid first name"),
        'last_name': field(validators="maxlen:100", error="invalid last name"),
    }


class UserInfoRequest(RequestRecord):
    fields = {
        'username': field(validators="required|minlen:1|maxlen:200", error="invalid username")
    }


class UserCommand(CliCommand):

    @property
    def svc_user(self) -> UserService:
        return self.get_di().get(DI_SERVICE_MANAGER).get(SVC_USER)


class UserCreateCmd(UserCommand):
    description = "create a new user"

    def arguments(self, parser: ArgumentParser):
        parser.add_argument('username', type=str, help="User name to create")
        parser.add_argument('email', type=str, help="User email")
        parser.add_argument('-f', '--first_name', help="First name", required=False)
        parser.add_argument('-l', '--last_name', help="First name", required=False)
        parser.add_argument('--enabled', default=True, action='store_true',
                            help="Enable user (default True)")
        parser.add_argument('--admin', default=False, action='store_true',
                            help="Create admin (default False)")

    def run(self, args) -> bool:

        req = UserCreateRequest()
        if not req.is_valid({'username': args.username, 'email': args.email}):
            for k, v in req.get_errors().items():
                self.tty.write(self.tty.colorizer.red("Error in {}: {}".format(k, v['*'])))
            return False

        if self.svc_user.get_by_username(args.username) is not None:
            self.tty.write(self.tty.colorizer.red("Error: username already exists"))
            return False

        record = UserRecord(username=args.username, email=args.email, admin=args.admin, active=args.enabled,
                            password="", first_name=args.first_name, last_name=args.last_name)
        id = self.svc_user.add_user(record)
        self.tty.write("Created user #{} with username '{}' and email '{}'".format(str(id), args.username, args.email))

        return True


class UserInfoCmd(UserCommand):
    description = "list user details"

    fields_labels = {
        'id': 'User Id',
        'username': 'Username',
        'active': 'Active',
        'admin': 'Administrator',
        'first_name': 'First name',
        'last_name': 'Last name',
        'email': 'Email adress',
        'creation_date': "Creation date",
        'last_login': "Last login",
        'attributes': "Attributes"
    }

    def arguments(self, parser: ArgumentParser):
        parser.add_argument('username', help="User name to search")

    def run(self, args) -> bool:

        req = UserInfoRequest()
        if not req.is_valid({'username': args.username}):
            for k, v in req.get_errors().items():
                self.tty.write(self.tty.colorizer.red("Error in {}: {}".format(k, v['*'])))
            return False

        record = self.svc_user.get_by_username(args.username)
        if record is None:
            self.tty.write(self.tty.colorizer.red("Error: username not found"))
            return False

        data = record.asdict()
        for field, label in self.fields_labels.items():
            print("{:<16}: {}".format(label, str(data[field])))

        return True


class UserModCmd(UserCommand):
    description = "change user details, including password"

    def arguments(self, parser: ArgumentParser):
        parser.add_argument('username', help="User name of account to change")
        parser.add_argument('-p', '--password', action='store_true', help="Change password")
        parser.add_argument('-a', '--noadmin', action='store_true',
                            help="Remove admin privileges")
        parser.add_argument('-A', '--admin', action='store_true',
                            help="Set admin privileges")
        parser.add_argument('-d', '--disabled',  action='store_true',
                            help="Disable user")
        parser.add_argument('-e', '--enabled', action='store_true',
                            help="Enable user")

    def run(self, args) -> bool:

        req = UserInfoRequest()
        if not req.is_valid({'username': args.username}):
            for k, v in req.get_errors().items():
                self.tty.write(self.tty.colorizer.red("Error in {}: {}".format(k, v['*'])))
            return False

        if not args.password and not args.noadmin and not args.admin and not args.enabled and not args.disabled:
            self.tty.write(self.tty.colorizer.red("Error: missing modification options"))
            return False

        if args.noadmin and args.admin:
            self.tty.write(self.tty.colorizer.red("Error: mutually exclusive options for admin privileges"))
            return False

        if args.disabled and args.enabled:
            self.tty.write(self.tty.colorizer.red("Error: mutually exclusive options for account status"))
            return False

        record = self.svc_user.get_by_username(args.username)
        if record is None:
            self.tty.write(self.tty.colorizer.red("Error: username not found"))
            return False

        changes = False
        if args.password:
            not_valid = True
            pwd = ""
            while not_valid:
                pwd = getpass.getpass('New password:')
                if len(pwd) == 0:
                    self.tty.write("operation aborted")
                    return False
                confirmation = getpass.getpass('Confirm password:')

                pwd = pwd.strip()
                confirmation = confirmation.strip()
                if pwd != confirmation:
                    self.tty.write(self.tty.colorizer.red("password and confirmation don't match, try again or press return to leave"))
                else:
                    not_valid = False

            if len(pwd) > 0:
                changes = True
                self.tty.write(self.tty.colorizer.green("> updated user password"))
                record.password = self.svc_auth.hash_pwd(pwd)

        if args.noadmin:
            if record.admin:
                changes = True
                self.tty.write(self.tty.colorizer.green("> removed admin privileges from user"))
            record.admin = False

        if args.admin:
            if not record.admin:
                changes = True
                self.tty.write(self.tty.colorizer.green("> added admin privileges to user"))
            record.admin = True

        if args.enabled:
            if not record.active:
                changes = True
                self.tty.write(self.tty.colorizer.green("> enabled user account"))
            record.active = True

        if args.disabled:
            if record.active:
                changes = True
                self.tty.write(self.tty.colorizer.green("> disabled user account"))
            record.active = False

        if changes:
            self.svc_user.update_user(record)
            self.tty.write("User account updated successfully")
        else:
            self.tty.write("User account already conforms to required changes")
        return True

    @property
    def svc_auth(self) -> AuthService:
        return self.get_di().get(DI_SERVICE_MANAGER).get(SVC_AUTH)
