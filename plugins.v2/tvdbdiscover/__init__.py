from typing import Any, List, Dict, Tuple, Optional

from cachetools import cached, TTLCache

from app import schemas
from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import DiscoverSourceEventData
from app.schemas.types import ChainEventType
from app.utils.http import RequestUtils


class JavDiscover(_PluginBase):
    # 插件名称
    plugin_name = "JavBus探索"
    # 插件描述
    plugin_desc = "让探索支持JavBus的数据浏览。"
    # 插件图标
    plugin_icon = "TheTVDB_A.png"
    # 插件版本
    plugin_version = "1.1"
    # 插件作者
    plugin_author = "fdulezi"
    # 作者主页
    author_url = "https://github.com/fdulezi"
    # 插件配置项ID前缀
    plugin_config_prefix = "javdiscover_"
    # 加载顺序
    plugin_order = 99
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _base_api = "http://192.168.31.252:38803/api/"
    _enabled = False
    _proxy = False
    _api_key = None

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._proxy = config.get("proxy")
            self._api_key = config.get("api_key")

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        获取插件API
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API说明"
        }]
        """
        return [{
            "path": "/javbus_discover",
            "endpoint": self.javbus_discover,
            "methods": ["GET"],
            "summary": "JavBus探索数据源",
            "description": "获取JavBus探索数据",
        }]

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'proxy',
                                            'label': '使用代理服务器',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'api_key',
                                            'label': 'API Key'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "proxy": False,
            "api_key": "ed2aa66b-7899-4677-92a7-67bc9ce3d93a"
        }

    def get_page(self) -> List[dict]:
        pass

    @cached(cache=TTLCache(maxsize=1, ttl=30 * 24 * 3600))

    @cached(cache=TTLCache(maxsize=32, ttl=1800))
    def __request(self, mtype: str, **kwargs):
        """
        请求JavBus API
        """
        api_url = f"{self._base_api}/movie"
        headers = {"Accept": "application/json","Content-Type": "application/json"}
        res = RequestUtils(headers=headers).get_res(
            api_url,
            params=kwargs
        )
        if res is None:
            raise Exception("无法连接JavBus，请检查网络连接！")
        if not res.ok:
            raise Exception(f"请求JavBus API失败：{res.text}")
        return res.json().get("movies")

    def javbus_discover(self, apikey: str, mtype: str = "movie",
                      company: int = None, contentRating: int = None, country: str = "usa",
                      genre: int = None, lang: str = "eng", sort: str = "score", sortType: str = "desc",
                      status: int = None, year: int = None,
                      page: int = 1, count: int = 30) -> List[schemas.MediaInfo]:
        """
        获取JavBus探索数据
        """

        def __movie_to_media(movie_info: dict) -> schemas.MediaInfo:
            """
            电影数据转换为MediaInfo
            {'date': '2025-03-28', 
                'id': 'DVEH-051', 
                'img': 'https://www.javbus.com/pics/thumb/b8xt.jpg', 
                'title': '出張マッサージ師の巨根に欲求不満を隠せないHもバリキャリなアラサー独女OLのピタパン尻誘惑 美咲かんな', 
                'tags': ['高清', '今日新種']
            }
            """
            return schemas.MediaInfo(
                type="电影",
                title=movie_info.get("title"),
                title_year=f"{movie_info.get('name')} ({movie_info.get('year')})",
                media_id=str(movie_info.get("id")),
                poster_path=movie_info.get('img')"
            )


        if apikey != settings.API_TOKEN:
            return []
        try:
            # 计算页码，TVDB为固定每页500条
            if page * count > 500:
                req_page = 500 // count
            else:
                req_page = page - 1
            result = self.__request(
                mtype,
                company=company,
                contentRating=contentRating,
                country=country,
                genre=genre,
                lang=lang,
                sort=sort,
                sortType=sortType,
                status=status,
                year=year,
                page=req_page
            )
        except Exception as err:
            logger.error(str(err))
            return []
        if not result:
            return []
        results = [__movie_to_media(movie) for movie in result]
        return results[(page - 1) * count:page * count]

    @staticmethod
    def javbus_filter_ui() -> List[dict]:
        """
        TheTVDB过滤参数UI配置
        """
        # 国家字典
        country_dict = {
            "usa": "美国",
            "chn": "中国",
            "jpn": "日本",
            "kor": "韩国",
            "ind": "印度",
            "fra": "法国",
            "ger": "德国",
            "ita": "意大利",
            "esp": "西班牙",
            "uk": "英国",
            "aus": "澳大利亚",
            "can": "加拿大",
            "rus": "俄罗斯",
            "bra": "巴西",
            "mex": "墨西哥",
            "arg": "阿根廷",
            "other": "其他"
        }

        cuntry_ui = [
            {
                "component": "VChip",
                "props": {
                    "filter": True,
                    "tile": True,
                    "value": key
                },
                "text": value
            } for key, value in country_dict.items()
        ]

        # 原始语种字典
        lang_dict = {
            "eng": "英语"
        }

        lang_ui = [
            {
                "component": "VChip",
                "props": {
                    "filter": True,
                    "tile": True,
                    "value": key
                },
                "text": value
            } for key, value in lang_dict.items()
        ]

        # 风格字典
        genre_dict = {
            "1": "Soap"
        }

        genre_ui = [
            {
                "component": "VChip",
                "props": {
                    "filter": True,
                    "tile": True,
                    "value": key
                },
                "text": value
            } for key, value in genre_dict.items()
        ]

        # 排序字典
        sort_dict = {
            "score": "评分",
            "firstAired": "首播日期",
            "name": "名称"
        }

        sort_ui = [
            {
                "component": "VChip",
                "props": {
                    "filter": True,
                    "tile": True,
                    "value": key
                },
                "text": value
            } for key, value in sort_dict.items()
        ]

        return [
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "类型"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "mtype"
                        },
                        "content": [
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "movies"
                                },
                                "text": "电影"
                            },
                            {
                                "component": "VChip",
                                "props": {
                                    "filter": True,
                                    "tile": True,
                                    "value": "series"
                                },
                                "text": "电视剧"
                            }
                        ]
                    }
                ]
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "风格"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "genre"
                        },
                        "content": genre_ui
                    }
                ]
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "国家"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "country"
                        },
                        "content": cuntry_ui
                    }
                ]
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "语言"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "lang"
                        },
                        "content": lang_ui
                    }
                ]
            },
            {
                "component": "div",
                "props": {
                    "class": "flex justify-start items-center"
                },
                "content": [
                    {
                        "component": "div",
                        "props": {
                            "class": "mr-5"
                        },
                        "content": [
                            {
                                "component": "VLabel",
                                "text": "排序"
                            }
                        ]
                    },
                    {
                        "component": "VChipGroup",
                        "props": {
                            "model": "sort"
                        },
                        "content": sort_ui
                    }
                ]
            }
        ]

    @eventmanager.register(ChainEventType.DiscoverSource)
    def discover_source(self, event: Event):
        """
        监听识别事件，使用ChatGPT辅助识别名称
        """
        if not self._enabled or not self._api_key:
            return
        event_data: DiscoverSourceEventData = event.event_data
        tvdb_source = schemas.DiscoverMediaSource(
            name="JavBus",
            mediaid_prefix="javbus",
            api_path=f"plugin/JavBusDiscover/javbus_discover?apikey={settings.API_TOKEN}",
            filter_params={
                "mtype": "series",
                "company": None,
                "contentRating": None,
                "country": "usa",
                "genre": None,
                "lang": "eng",
                "sort": "score",
                "sortType": "desc",
                "status": None,
                "year": None,
            },
            filter_ui=self.javbus_filter_ui()
        )
        if not event_data.extra_sources:
            event_data.extra_sources = [tvdb_source]
        else:
            event_data.extra_sources.append(tvdb_source)

    def stop_service(self):
        """
        退出插件
        """
        pass
