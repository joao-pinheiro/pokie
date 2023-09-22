from argparse import ArgumentParser

from pokie.constants import DI_SERVICES, DI_APP
from pokie.contrib.base.constants import SVC_FIXTURE
from pokie.contrib.base.dto import FixtureRecord
from pokie.contrib.base.service.fixture import FixtureService
from pokie.core import CliCommand


class FixtureCmd(CliCommand):
    @property
    def svc_fixture(self) -> FixtureService:
        return self.get_di().get(DI_SERVICES).get(SVC_FIXTURE)


class RunFixtureCmd(FixtureCmd):
    description = "run existing fixtures"

    def arguments(self, parser: ArgumentParser):
        parser.add_argument("name", type=str, help="fixture name(s) to run", nargs="*")

    def valid_name(self, name: str) -> bool:
        return "." in name

    def run(self, args) -> bool:
        all = self.svc_fixture.scan() if len(args.name) == 0 else args.name

        existing = [r.name for r in self.svc_fixture.list()]
        for name in all:
            if self.valid_name(name):
                self.tty.write(f"Fixture {name}: ", eol=False)
                if name in existing:
                    self.tty.write(
                        self.tty.colorizer.white(
                            "already executed, skipping", attr="bold"
                        )
                    )
                else:
                    try:
                        self.svc_fixture.execute(name)
                        self.svc_fixture.add(FixtureRecord(name=name))
                        self.tty.write(
                            self.tty.colorizer.green(
                                "executed successfully", attr="bold"
                            )
                        )
                    except Exception as e:
                        self.tty.error("\nError : " + str(e))
                        return False
            else:
                self.tty.error(f"Fixture '{name}': invalid name, skipping")
        return True


class CheckFixtureCmd(FixtureCmd):
    description = "show existing fixture status"

    def run(self, args) -> bool:
        all = self.svc_fixture.scan()
        if len(all) != len(set(all)):
            # @todo: use rick.util.misc.list_duplicates()
            duplicates = []
            seen = set()
            for item in all:
                if item in seen:
                    duplicates.append(item)
                else:
                    seen.add(item)
            self.tty.error(f'Duplicated fixture(s) found: {",".join(duplicates)}')
            return False

        existing = [r.name for r in self.svc_fixture.list()]
        for name in all:
            self.tty.write(f"Fixture {name}: ", eol=False)
            if name in existing:
                self.tty.write(
                    self.tty.colorizer.white("already executed, skipping", attr="bold")
                )
            else:
                self.tty.write(self.tty.colorizer.green("new fixture", attr="bold"))
        return True
