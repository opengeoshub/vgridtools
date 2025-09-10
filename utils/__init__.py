from qgis.core import QgsApplication

LOC = QgsApplication.locale()[:2]

def tr(*string):
    # Translate to Vietnamese: arg[0] - English (translate), arg[1] - Vietnamese
    if LOC == "vi":
        if len(string) == 2:
            return string[1]
        else:
            return string[0]
    else:
        return string[0]