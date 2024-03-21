import asyncio
import json
from datetime import date as datelib
from datetime import timedelta
from typing import TypedDict

from dotenv import get_key
from fusion_stat import App, Competition, Matches
from httpx import AsyncClient
from tqdm import tqdm

TEST_HTTP_PROXY = get_key(".env", "TEST_HTTP_PROXY")
DELAY = 2


class SSCompetitionDict(TypedDict):
    name: str
    logo: str


class SSTeamDict(TypedDict):
    name: str
    logo: str
    shots: int
    xg: float
    score: int | None
    played: int


class SSMatchDict(TypedDict):
    name: str
    utc_time: str
    finished: bool
    competition: SSCompetitionDict
    home: SSTeamDict
    away: SSTeamDict


SSMatchesDict = dict[str, list[SSMatchDict]]


def generate_recent_dates() -> list[str]:
    today = datelib.today()
    dates = [
        (today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-1, 3)
    ]
    return dates


def parse_coms_and_teams(
    coms_list: list[Competition],
) -> tuple[dict[str, SSCompetitionDict], dict[str, SSTeamDict]]:
    coms_dict: dict[str, SSCompetitionDict] = {}
    teams_dict: dict[str, SSTeamDict] = {}
    for com in coms_list:
        coms_dict[com.info["id"]] = SSCompetitionDict(
            name=com.info["name"],
            logo=com.info["logo"],
        )

        for team in com.get_teams():
            teams_dict[team["id"]] = SSTeamDict(
                name=team["name"],
                logo=team["logo"],
                shots=team["shooting"]["shots"],
                xg=team["shooting"]["xg"],
                score=None,
                played=team["played"],
            )

    return coms_dict, teams_dict


def parse_matches(
    matches: Matches,
    coms_dict: dict[str, SSCompetitionDict],
    teams_dict: dict[str, SSTeamDict],
) -> list[SSMatchDict]:
    ss_matches: list[SSMatchDict] = []
    if items := matches.get_items():
        for match in items:
            com = coms_dict[match["competition"]["id"]]

            home = teams_dict[match["home"]["id"]]
            away = teams_dict[match["away"]["id"]]
            home["score"] = match["home"]["score"]
            away["score"] = match["away"]["score"]

            match = SSMatchDict(
                name=match["name"],
                utc_time=match["utc_time"],
                finished=match["finished"],
                competition=com,
                home=home,
                away=away,
            )
            ss_matches.append(match)
    return ss_matches


def export(data: SSMatchesDict, file: str) -> None:
    with open(file, "w") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))


async def main() -> None:
    client = AsyncClient(proxies=TEST_HTTP_PROXY)
    app = App(client=client)
    with tqdm(total=10) as pbar:
        coms = await app.get_competitions()
        await asyncio.sleep(DELAY)
        pbar.update(1)

        coms_list: list[Competition] = []
        for params in coms.get_params():
            com = await app.get_competition(**params)
            await asyncio.sleep(DELAY)
            pbar.update(1)
            coms_list.append(com)

        coms_dict, teams_dict = parse_coms_and_teams(coms_list)

        dates = generate_recent_dates()
        matches_dict: SSMatchesDict = {}
        for date in dates:
            matches = await app.get_matches(date=date)
            await asyncio.sleep(DELAY)
            pbar.update(1)
            matches_dict[date] = parse_matches(matches, coms_dict, teams_dict)

    await app.close()
    export(matches_dict, "matches.json")


if __name__ == "__main__":
    asyncio.run(main())
