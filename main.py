import asyncio
import json
import os
from typing import Any
from datetime import date as datelib, timedelta

from pydantic import BaseModel
from dotenv import load_dotenv
from httpx import AsyncClient
from fusion_stat import Competitions, Competition, Matches
from tqdm import tqdm


# 读取环境变量
load_dotenv()


def read_env(name: str) -> str:
    if (value := os.getenv(name)) is not None:
        return value
    return ""


TEST_HTTP_PROXY = read_env("TEST_HTTP_PROXY")
DELAY = 2


class CompetitionModel(BaseModel):
    name: str
    logo: str


class TeamModel(BaseModel):
    name: str
    logo: str
    shots: int
    xg: float
    score: int | None
    played: int


class MatchModel(BaseModel):
    name: str
    utc_time: str
    finished: bool
    competition: CompetitionModel
    home: TeamModel
    away: TeamModel


def generate_recent_dates() -> list[str]:
    today = datelib.today()
    dates = [
        (today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-1, 3)
    ]
    return dates


async def get_coms_index(
    client: AsyncClient,
    pbar: tqdm,
) -> list[dict[str, Any]]:
    coms = Competitions(client=client)
    fusion = await coms.gather()
    pbar.update(1)
    return fusion.index()


async def get_competitions_and_teams(
    client: AsyncClient,
    coms_index: list[dict[str, Any]],
    pbar: tqdm,
) -> tuple[dict[str, Any], dict[str, Any]]:
    competitions = {}
    teams = {}
    for params in coms_index:
        await asyncio.sleep(DELAY)

        com = Competition(**params, client=client)
        fusion = await com.gather()
        pbar.update(1)

        competitions[fusion.info["id"]] = fusion.info

        for team in fusion.teams:
            teams[team["id"]] = team

    return competitions, teams


async def get_matches(
    client: AsyncClient,
    competitions: dict[str, Any],
    teams: dict[str, Any],
    pbar: tqdm,
) -> dict[str, list[Any]]:
    matches_data = {}
    dates = generate_recent_dates()
    for date in dates:
        await asyncio.sleep(DELAY)

        matches = Matches(date=date, client=client)
        fusion = await matches.gather()
        pbar.update(1)

        day_matches = []
        if fusion.info["matches"]:
            for match in fusion.info["matches"]:
                competition = CompetitionModel(
                    name=match["competition"]["name"],
                    logo=competitions[match["competition"]["id"]]["logo"],
                )

                if match["score"]:
                    home_score, away_score = [
                        int(score) for score in match["score"].split(" - ")
                    ]
                else:
                    home_score, away_score = None, None

                home_team = teams[match["home"]["id"]]
                home = TeamModel(
                    name=home_team["name"],
                    logo=home_team["logo"],
                    shots=home_team["shooting"]["shots"],
                    xg=home_team["shooting"]["xg"],
                    score=home_score,
                    played=home_team["played"],
                )

                away_team = teams[match["away"]["id"]]
                away = TeamModel(
                    name=away_team["name"],
                    logo=away_team["logo"],
                    shots=away_team["shooting"]["shots"],
                    xg=away_team["shooting"]["xg"],
                    score=away_score,
                    played=away_team["played"],
                )

                match_data = MatchModel(
                    name=match["name"],
                    utc_time=match["utc_time"],
                    finished=match["finished"],
                    competition=competition,
                    home=home,
                    away=away,
                )
                day_matches.append(match_data.model_dump())
        matches_data[date] = day_matches
    return matches_data


def export(data: dict[str, Any], file: str) -> None:
    with open(file, "w") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))


async def main() -> None:
    async with AsyncClient(proxies=TEST_HTTP_PROXY) as client:
        with tqdm(total=10) as pbar:
            coms_index = await get_coms_index(client, pbar)
            competitions, teams = await get_competitions_and_teams(
                client, coms_index, pbar
            )
            matches = await get_matches(client, competitions, teams, pbar)
    export(matches, "matches.json")


if __name__ == "__main__":
    asyncio.run(main())
