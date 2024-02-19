from enum import Enum


class Action(Enum):
    SEE_SHOPPING_LIST = "see_shopping_list"
    ADD_TO_SHOPPING_LIST = "add_to_shopping_list"
    REMOVE_FROM_SHOPPING_LIST = "remove_from_shopping_list"
    SEE_PANTRY = "see_pantry"
    ADD_TO_PANTRY = "add_to_pantry"
    REMOVE_FROM_PANTRY = "remove_from_pantry"
    MODIFY_RECIPE = "modify_recipe"
