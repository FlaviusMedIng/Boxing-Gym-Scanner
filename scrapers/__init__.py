from scrapers.acheter_louer import AcheterLouerScraper
from scrapers.comparis import ComparisScraper
from scrapers.homegate import HomegateScraper
from scrapers.immobilier_ch import ImmobilierChScraper
from scrapers.moservernet import MoserVernetScraper
from scrapers.naef import NaefScraper
from scrapers.netimmo import NetimmoScraper
from scrapers.pilet_renaud import PiletRenaudScraper
from scrapers.realadvisor import RealAdvisorScraper
from scrapers.rosset import RossetScraper


def build_scrapers(config: dict, logger):
    mapping = {
        "homegate": HomegateScraper,
        "realadvisor": RealAdvisorScraper,
        "rosset": RossetScraper,
        "pilet_renaud": PiletRenaudScraper,
        "comparis": ComparisScraper,
        "immobilier_ch": ImmobilierChScraper,
        "acheter_louer": AcheterLouerScraper,
        "naef": NaefScraper,
        "moservernet": MoserVernetScraper,
        "netimmo": NetimmoScraper,
    }
    scrapers = []
    for key, cls in mapping.items():
        site_cfg = config["sites"].get(key, {})
        if site_cfg.get("enabled"):
            scrapers.append(cls(site_cfg, config, logger))
    return scrapers
