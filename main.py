import pygame as pg
from vectors_likeablejuniper import Vector
import ctypes
import random
import time
import json


user32 = ctypes.windll.user32
screensize = Vector(user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
screencenter = 0.5 * screensize

### Parameters ###
buttonScale = 1 #reduce this to increase amount of buttons that can be displayed without overflow, default: 1, range: (0, 1]
useFullscreen = False #should the game be launched in fullscreen or not, default: False
windowResizeFactor = 0.8 #in case fullscreen isn't used, how big, relative to the entire screen size, should the window be? default: 0.8, range: (0, 1]
deltaModeEnabled = True #whether or not placed flags should reduce adjacent cell's count by 1. Can be changed during runtime by button press, default: True
### End Parameters ###

pg.init()
if useFullscreen:
    windowSize = screensize
    windowCenter = screencenter
    screen = pg.display.set_mode((0, 0), pg.FULLSCREEN) #(0, 0) makes fullscreen window fit to screen size without being stretched
else:
    screen = pg.display.set_mode((windowSize := (screensize*windowResizeFactor)).components)
    windowCenter = windowSize*0.5

pg.display.set_caption("2D-Minesweeper")
pg.display.set_icon(pg.image.load("Assets/mine.png"))

pg.font.init()
mainFont = pg.font.SysFont("Roboto", int(2/35*windowSize[0]), False, False)
titleFont = pg.font.SysFont("Roboto", int(3/40*windowSize[0]), False, False)
countFont = pg.font.SysFont("Roboto", int(1/35*windowSize[0]*buttonScale), False, False)


def convertTime(seconds):
    if seconds == "-":
        return seconds
    minutes = int(seconds // 60)
    seconds  = round(seconds - minutes*60, 1)
    return "{}:{}".format(minutes, seconds)


class Text:
    def __init__(self, center, font: pg.font.Font, text=None):
        self.center = center
        self.font = font
        if text:
            self.textObj = self.font.render(text, True, (0, 0, 0))
            self.textRect = self.textObj.get_rect(center=self.center)
    
    def __call__(self, screen: pg.Surface, dynamicText=None):
        if dynamicText:
            textObj = self.font.render(dynamicText, True, (0, 0, 0))
            textRect = textObj.get_rect(center=self.center)
            screen.blit(textObj, textRect)
        else:
            screen.blit(self.textObj, self.textRect)


class TimeText:
    def __init__(self, center):
        self.startTime = time.time()
        self.lastPausedTime = self.startTime
        self.paused = False
        #prevent time text from moving around from recentering every call by setting position on initiate
        textObj = mainFont.render(convertTime(0), True, (0, 0, 0))
        textRect = textObj.get_rect(center=center)
        self.position = textRect[:2]
    
    def __call__(self, screen: pg.Surface):
        seconds = (self.lastPausedTime if self.paused else time.time()) - self.startTime
        text = convertTime(seconds)
        textObj = mainFont.render(text, True, (0, 0, 0))
        screen.blit(textObj, self.position)

    def restartClock(self):
        self.startTime = time.time()
        self.paused = False

    def pause(self):
        self.paused = True
        self.lastPausedTime = time.time()
    
    def currentClock(self):
        return (self.lastPausedTime if self.paused else time.time()) - self.startTime


class Button:
    def __init__(self, position: Vector, coordinates: Vector, dimensions: Vector, colors: list[list[int, int, int]], flagImage: pg.Surface, mineImage: pg.Surface):
        self.position = position #position on the screen
        self.coordinates = coordinates #position in the field
        self.dimensions = dimensions
        self.center = self.position + self.dimensions/2
        self.colors = colors
        self.count = 0
        self.displayCount = 0
        self.isMine = False
        self.revealed = False
        self.flagged = False

        self.flagImage = flagImage
        self.flagRect = self.flagImage.get_rect()
        self.flagRect.center = self.center

        self.mineImage = mineImage
        self.mineRect = self.mineImage.get_rect()
        self.mineRect.center = self.center - Vector([round(windowSize[0]/1500) for _ in range(2)]) #centering is approximately 1 pixel offset, reverse that        

    def __repr__(self):
        return str("Button(revealed: {}, flagged: {}, isMine: {})".format(self.revealed, self.flagged, self.isMine))
    
    def __call__(self, screen: pg.Surface, field, fieldDimensions, mouseData):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        
        currentColor = self.colors[3] if self.revealed else self.colors[int(isHovered) + int((islClick or isrClick) and isHovered)] #allows the button to assume three different colors based on whether its neutral, hovered or clicked
        pg.draw.rect(screen, currentColor, self.position.components + self.dimensions.components)
        
        if self.flagged:
            screen.blit(self.flagImage, self.flagRect)
        elif self.revealed:
            if self.isMine:
                screen.blit(self.mineImage, self.mineRect)
            elif self.displayCount != 0:
                renderedFont = countFont.render(str(self.displayCount), True, numberColors[self.displayCount%len(numberColors)])
                countRect = renderedFont.get_rect()
                countRect.center = self.center
                screen.blit(renderedFont, countRect)

        if isHovered and isNewClick:
            if isrClick and not self.revealed:
                self.flagged = bool((int(self.flagged) + 1) % 2)
            
            if islClick and not self.revealed and not self.flagged:
                field = self.reveal(field, fieldDimensions)
            
        return field, isHovered


    def highlight_adjacent(self, field, screen, useDelta):
        pg.draw.rect(screen, self.colors[5], self.position.components + self.dimensions.components, 2)
        for xShift in range(-1, 2):
            for yShift in range(-1, 2):
                targetCoords = self.coordinates + Vector(xShift, yShift)
                if Vector(0, 0) <= targetCoords < fieldDimensions: #make sure coordinates are inside the field
                    targetCell: Button = field[targetCoords[0]][targetCoords[1]]
                    if not (targetCell.revealed or (targetCell.flagged and useDelta)): #only highlight if target isn't revealed and isn't flagged (logical simplification of "not A and not (B and x)" to "not (A or (B and x))")
                        pg.draw.rect(screen, targetCell.colors[4], targetCell.position.components + targetCell.dimensions.components, 2)


    def reveal(self, field, fieldDimensions):
        self.revealed = True
        if self.count == 0: #ignore delta and only reveal if the cell actually has no mines surrounding it, as the user may have placed some false flags
            for xShift in range(-1, 2):
                for yShift in range(-1, 2):
                    shiftVector = Vector(xShift, yShift)
                    revealCoords = self.coordinates + shiftVector
                    if Vector(0, 0) <= revealCoords < fieldDimensions: #make sure coordinates are inside the field
                        targetButton: Button = field[revealCoords[0]][revealCoords[1]]
                        if not targetButton.revealed:
                            field = targetButton.reveal(field, fieldDimensions) #recursive call to reveal groups of zeroes
        
        return field


    def updateCount(self, field: list[list[list["Button"]]], fieldDimensions, useDelta):
        self.count = 0
        surroundingFlags = 0
        for xShift in range(-1, 2):
            for yShift in range(-1, 2):
                shiftVector = Vector(xShift, yShift)
                checkCoords = self.coordinates + shiftVector
                if Vector(0, 0) <= checkCoords < fieldDimensions: #make sure coordinates are inside the field
                        targetCell: Button = field[checkCoords[0]][checkCoords[1]]
                        self.count += int(targetCell.isMine)
                        surroundingFlags += int(targetCell.flagged)
        self.displayCount = self.count - [0, surroundingFlags][int(useDelta)]


class DeltaButton:
    """Specifically for a button which has a toggleable function and displays whether or not its toggled"""
    def __init__(self, center: Vector, dimensions: Vector, colors, text):
        self.position = center - 0.5*dimensions
        self.dimensions = dimensions
        self.colors = colors
        self.textObj = mainFont.render(text, True, (0, 0, 0))
        textRect = self.textObj.get_rect(center=[center[0]-self.dimensions[0]*0.5, center[1]])
        textRect.centerx -= textRect.width*0.5 + 10
        self.textRect = textRect
        self.crossRectScale = 0.6
        self.crossRect = (self.position+self.dimensions*(1-self.crossRectScale)/2).components + (self.dimensions*self.crossRectScale).components

    def __call__(self, screen: pg.Surface, mouseData, deltaModeEnabled):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        isNewlClick = islClick and isNewClick

        screen.blit(self.textObj, self.textRect)

        pg.draw.rect(screen, self.colors[int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components) #ground color
        pg.draw.rect(screen, self.colors[2+int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components, 3) #border color

        if deltaModeEnabled:
            pg.draw.line(screen, (161, 7, 2), self.crossRect[:2], (Vector(self.crossRect[:2])+self.dimensions*self.crossRectScale).components, 3)
            pg.draw.line(screen, (161, 7, 2), (Vector(self.crossRect[:2])+Vector(self.dimensions[0]*self.crossRectScale, 0)).components, (Vector(self.crossRect[:2])+Vector(0, self.dimensions[0]*self.crossRectScale)).components, 3)

        if isNewlClick and isHovered:
            deltaModeEnabled = bool((int(deltaModeEnabled)+1) % 2)

        return deltaModeEnabled


class TimedModeButton:
    """Specifically for a button which has a toggleable function and displays whether or not its toggled"""
    def __init__(self, center: Vector, dimensions: Vector, colors, text):
        self.position = center - 0.5*dimensions
        self.dimensions = dimensions
        self.colors = colors
        self.textObj = mainFont.render(text, True, (0, 0, 0))
        textRect = self.textObj.get_rect(center=[center[0]-self.dimensions[0]*0.5, center[1]])
        textRect.centerx -= textRect.width*0.5 + 10
        self.textRect = textRect
        self.crossRectScale = 0.6
        self.crossRect = (self.position+self.dimensions*(1-self.crossRectScale)/2).components + (self.dimensions*self.crossRectScale).components

    def __call__(self, screen: pg.Surface, mouseData, isTimed):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        isNewlClick = islClick and isNewClick

        screen.blit(self.textObj, self.textRect)

        pg.draw.rect(screen, self.colors[int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components) #ground color
        pg.draw.rect(screen, self.colors[2+int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components, 3) #border color

        if isTimed:
            pg.draw.line(screen, (161, 7, 2), self.crossRect[:2], (Vector(self.crossRect[:2])+self.dimensions*self.crossRectScale).components, 3)
            pg.draw.line(screen, (161, 7, 2), (Vector(self.crossRect[:2])+Vector(self.dimensions[0]*self.crossRectScale, 0)).components, (Vector(self.crossRect[:2])+Vector(0, self.dimensions[0]*self.crossRectScale)).components, 3)

        if isNewlClick and isHovered:
            isTimed = bool((int(isTimed)+1) % 2)

        return isTimed


class MainMenuButton:
    def __init__(self, center: Vector, dimensions: Vector, colors, icon: pg.Surface):
        self.position = center - 0.5*dimensions
        self.center = center
        self.dimensions = dimensions
        self.colors = colors
        self.icon = pg.transform.scale(icon, self.dimensions*0.6)
        self.iconRect = self.icon.get_rect()
        self.iconRect.center = self.center
    
    def __call__(self, screen, mouseData, virtualLocation):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        isNewlClick = islClick and isNewClick

        pg.draw.rect(screen, self.colors[int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components) #ground color
        pg.draw.rect(screen, self.colors[2+int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components, 3) #border color

        screen.blit(self.icon, self.iconRect)

        if isNewClick and isHovered:
            virtualLocation = LOC_MAIN_MENU

        return virtualLocation


class DifficultySelectButton:
    def __init__(self, center: Vector, dimensions: Vector, colors, text, difficultySettings: list[list[int, int], int, bool]):
        self.position = center - 0.5*dimensions
        self.center = center
        self.dimensions = dimensions
        self.colors = colors
        self.textObj = mainFont.render(text, True, (0, 0, 0))
        self.textRect = self.textObj.get_rect(center=self.center)
        self.difficultySettings = difficultySettings
    
    def __call__(self, screen: pg.Surface, field, fieldDimensions: Vector, mineAmount, mouseData, virtualLocation, currentDifficulty):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        isNewlClick = islClick and isNewClick

        pg.draw.rect(screen, self.colors[int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components) #ground color
        pg.draw.rect(screen, self.colors[2+int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components, 3) #border color
        screen.blit(self.textObj, self.textRect)

        if isNewlClick and isHovered:
            fieldDimensions = self.difficultySettings[0]
            mineAmount = self.difficultySettings[1]

            fieldStartPos = (windowSize - (Vector(fieldDimensions.components[:2])-Vector(1, 1))*(buttonSize+buttonMargin)) / 2 #where the top left corner of the field is placed, will be set again once fieldDimensions is defined after selecting difficulty

            field: list[list[Button]] = [[Button(fieldStartPos + Vector(x, y)*(buttonSize+buttonMargin), Vector(x, y), buttonSizeVector, buttonColors, flagImage, mineImage) for y in range(fieldDimensions[1])] for x in range(fieldDimensions[0])]

            #randomly distribute the mines in the field
            for _ in range(mineAmount):
                while field[(xCoord := random.randint(0, fieldDimensions[0]-1))][(yCoord := random.randint(0, fieldDimensions[1]-1))].isMine:
                    continue
                field[xCoord][yCoord].isMine = True
            
            for xi, x in enumerate(field):
                for yi, y in enumerate(x):
                    y.updateCount(field, fieldDimensions, False)

            #find a suitable start
            while field[(xCoord := random.randint(0, fieldDimensions[0]-1))][(yCoord := random.randint(0, fieldDimensions[1]-1))].count != 0:
                continue
            field = field[xCoord][yCoord].reveal(field, fieldDimensions)
        


            return field, self.difficultySettings[0], self.difficultySettings[1], [LOC_INGAME_UNTIMED, LOC_INGAME_TIMED][self.difficultySettings[2]], self.difficultySettings[3]

        return field, fieldDimensions, mineAmount, virtualLocation, currentDifficulty


class ExitButton:
    def __init__(self, center: Vector, dimensions: Vector, colors):
        self.position = center - 0.5*dimensions
        self.center = center
        self.dimensions = dimensions
        self.colors = colors
        self.textObj = mainFont.render("Exit", True, (0, 0, 0))
        self.textRect = self.textObj.get_rect(center=self.center)
    
    def __call__(self, screen: pg.Surface, mouseData, virtualLocation):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        isNewlClick = islClick and isNewClick

        pg.draw.rect(screen, self.colors[int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components) #ground color
        pg.draw.rect(screen, self.colors[2+int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components, 3) #border color

        screen.blit(self.textObj, self.textRect)

        if isNewlClick and isHovered:
            return LOC_EXIT

        return virtualLocation


class GenericLocationButton:
    def __init__(self, center: Vector, dimensions: Vector, colors, text, targetLocation):
        self.position = center - 0.5*dimensions
        self.center = center
        self.dimensions = dimensions
        self.colors = colors
        self.textObj = mainFont.render(text, True, (0, 0, 0))
        self.textRect = self.textObj.get_rect(center=self.center)
        self.targetLocation = targetLocation
    
    def __call__(self, screen: pg.Surface, mouseData, virtualLocation):
        mousePos, islClick, isrClick, isNewClick = mouseData
        isHovered = self.position < mousePos < self.position + self.dimensions
        isNewlClick = islClick and isNewClick

        pg.draw.rect(screen, self.colors[int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components) #ground color
        pg.draw.rect(screen, self.colors[2+int(isHovered)+int(islClick and isHovered)], self.position.components+self.dimensions.components, 3) #border color
        screen.blit(self.textObj, self.textRect)

        if isNewlClick and isHovered:
            return self.targetLocation

        return virtualLocation


class InputField:
    def __init__(self, center: Vector, dimensions: Vector, text, ):
        self.center = center
        self.dimensions = dimensions
        self.position = self.center - 0.5*self.dimensions
        self.text = text


def checkWin(field: list[list[list[Button]]], cellAmount, mineAmount) -> tuple[bool, bool]:
    """Returns tuple in format (bool, bool). The first bool indicates whether or not the game is won, the second whether or not the clock should be stopped."""
    revealedCount = 0
    for xi, x in enumerate(field):
        for yi, y in enumerate(x):
            if y.revealed:
                revealedCount += 1
                if y.isMine: return False, True #if a mine has been uncovered, you cannot win the game anymore but the timer should be paused
    
    if revealedCount == cellAmount-mineAmount: #if all non-mine cells have been revealed
        return True, True
    
    return False, False


def renderIngameFrame(field: list[list[Button]], fieldDimensions: Vector, screen: pg.Surface, mouseData: tuple[tuple, bool, bool, bool], deltaModeButton: DeltaButton, deltaModeEnabled: bool, mineData: tuple[int, Vector, list], mainMenuButton: MainMenuButton, virtualLocation: int, difficulty: str, highscores: dict[float, float, float]):
    mineAmount, mineCountCenter, mineCountColors = mineData

    hoveredCoords = None
    flagCount = 0
    for xi, x in enumerate(field):
        for yi, y in enumerate(x):
            if y.flagged:
                flagCount += 1
            field, isHovered = y(screen, field, fieldDimensions, mouseData)
            y.updateCount(field, fieldDimensions, deltaModeEnabled)
            if isHovered:
                hoveredCoords = Vector(xi, yi)
    
    winData = checkWin(field, fieldDimensions[0]*fieldDimensions[1], mineAmount)

    if winData[1] and not timeText.paused:
        timeText.pause()
    
    if winData[0] and virtualLocation == LOC_INGAME_TIMED:
        if timeText.currentClock() < highscores[difficulty] or (highscores[difficulty] == -1): #if no highscore has been set yet, set it to the current time
            highscores[difficulty] = timeText.currentClock()

    if hoveredCoords:
        field[hoveredCoords[0]][hoveredCoords[1]].highlight_adjacent(field, screen, deltaModeEnabled)

    deltaModeEnabled = deltaModeButton(screen, mouseData, deltaModeEnabled)
    virtualLocation = mainMenuButton(screen, mouseData, virtualLocation)
    
    mineCountRender = mainFont.render("Mines left: {}".format(mineAmount-flagCount), True, mineCountColors[int(flagCount>mineAmount)])
    mineCountRect = mineCountRender.get_rect(center=mineCountCenter)
    screen.blit(mineCountRender, mineCountRect)

    if virtualLocation == LOC_INGAME_TIMED:
        timeText(screen)

    return virtualLocation, field, deltaModeEnabled, highscores


def renderMainMenuFrame(screen: pg.Surface, mouseData: tuple[tuple, bool, bool, bool], isTimed, highscores):

    virtualLocation = LOC_MAIN_MENU

    difficulty = DIFFICULTY_DEFAULT #when difficulty changes, this will not be called again before moving into the game

    field = fieldDimensions = mineAmount = None

    titleText(screen)

    for i, iterDifficulty in enumerate(difficultyList[:-1]):
        field, fieldDimensions, mineAmount, virtualLocation, difficulty = difficultySelectButtons[i](screen, field, fieldDimensions, mineAmount, mouseData, virtualLocation, difficulty)
        difficultyHighscoreTexts[i](screen, convertTime(highscores[iterDifficulty] if highscores[iterDifficulty] > 0 else "-"))
    
    isTimed = timedModeButton(screen, mouseData, isTimed)

    if virtualLocation > 0: #if a new difficulty has been selected, reset the time
        if isTimed:
            virtualLocation = LOC_INGAME_TIMED
            timeText.restartClock()
    
    virtualLocation = customModeButton(screen, mouseData, virtualLocation)

    virtualLocation = exitButton(screen, mouseData, virtualLocation)

    return virtualLocation, field, fieldDimensions, isTimed, mineAmount, difficulty


def renderCustomMenuFrame(screen, mouseData):
    virtualLocation = LOC_CUSTOM_MENU
    field = fieldDimensions = mineAmount = None

    customModeTitle(screen)

    virtualLocation = mainMenuButton(screen, mouseData, virtualLocation)

    return virtualLocation, field, fieldDimensions, mineAmount


buttonSize = min(windowSize)/(30/buttonScale)
buttonSizeVector = Vector(buttonSize for _ in range(2)) #buttons are always square
buttonMargin = windowSize[0]/(300/buttonScale)
fieldDimensions = Vector(5, 15)
fieldStartPos = (windowSize - (Vector(fieldDimensions.components[:2])-Vector(1, 1))*(buttonSize+buttonMargin)) / 2 #where the top left corner of the field is placed, will be set again once fieldDimensions is defined after selecting difficulty
mineCountCenter = Vector(windowCenter[0], windowSize[1]/10)

defaultButtonColors = [(23, 55, 83), (27, 67, 83), (33, 118, 156), (52, 119, 163), (39, 123, 179), (22, 130, 201)] #passive ground color, hovered ground color, clicked ground color, passive border color, hovered border color, clicked border color
buttonColors = [(55, 74, 84), (81, 117, 135), (116, 176, 207), (186, 181, 255), (52, 207, 235), (173, 2, 119)] #passive color, hovered color, clicked color, revealed color, highlight color (hidden), highlight color (revealed)
numberColors = [(0, 0, 0), (55, 41, 255), (0, 156, 18), (240, 24, 24), (195, 0, 230), (255, 215, 36), (0, 138, 207), (116, 32, 161), (252, 3, 161)]
deltaButtonColors = defaultButtonColors
mainMenuButtonColors = defaultButtonColors
difficultyButtonColors = defaultButtonColors
exitButtonColors = defaultButtonColors
timedModeButtonColors = defaultButtonColors
customModeButtonColors = defaultButtonColors
mineCountColors = [(0, 0, 0), (191, 34, 34)]

deltaModeButton = DeltaButton(Vector(windowSize[0]-buttonSize*5, windowSize[1]/10), Vector(max(windowSize[0]/24, 20) for _ in range(2)), deltaButtonColors, "Δ")
mainMenuButton = MainMenuButton(Vector(buttonSize*5, windowSize[1]/10), Vector(max(windowSize[0]/24, 20) for _ in range(2)), mainMenuButtonColors, pg.image.load("Assets/back_arrow.png"))

titleText = Text(Vector(windowCenter[0], windowSize[1]/7), titleFont, "3D Minesweeper")
timeText = TimeText(Vector(windowSize[0]*0.5, windowSize[1]*0.9))
timedModeButton = TimedModeButton(Vector(windowSize[0]-buttonSize*5, windowSize[1]/10), Vector(max(windowSize[0]/24, 20) for _ in range(2)), timedModeButtonColors, "Timed:")

with open("highscores.json", "r") as f:
    highscores = json.load(f)

DIFFICULTY_DEFAULT = 0
#these are named for easy access to dictionary via dict[difficulty]
DIFFICULTY_EASY = "easy"
DIFFICULTY_MEDIUM = "medium"
DIFFICULTY_HARD = "hard"
DIFFICULTY_CUSTOM = "custom"
difficultyList = (DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD, DIFFICULTY_CUSTOM)
difficultyNames = {DIFFICULTY_EASY: "Easy", DIFFICULTY_MEDIUM: "Medium", DIFFICULTY_HARD: "Hard", DIFFICULTY_CUSTOM: "Custom"}
difficultySettingDict = {DIFFICULTY_EASY: (Vector(10, 10), 6, False, DIFFICULTY_EASY), DIFFICULTY_MEDIUM: (Vector(17, 15), 30, False, DIFFICULTY_MEDIUM), DIFFICULTY_HARD: (Vector(30, 19), 60, False, DIFFICULTY_HARD)}
difficulty = DIFFICULTY_DEFAULT

LOC_MAIN_MENU = 0
LOC_INGAME_UNTIMED = 1
LOC_INGAME_TIMED = 2
LOC_CUSTOM_MENU = 3
LOC_EXIT = -1 #will be set to -1 for one frame before quitting the game
virtualLocation = LOC_MAIN_MENU
isIngame = lambda virtualLocation: virtualLocation in (LOC_INGAME_UNTIMED, LOC_INGAME_TIMED)
isTimed = False

difficultyButtonSpread = 0.2
difficultyButtonOffset = Vector(0, windowSize[1]*0.1)
highscoreDisplayOffset = Vector(windowSize[0]/6+windowSize[0]/12, 0)
difficultySelectButtons: list[DifficultySelectButton] = []
difficultyHighscoreTexts: list[Text] = []
for i, iterDifficulty in enumerate(difficultyList[:-1]):
    difficultySelectButtons.append(DifficultySelectButton(difficultyButtonOffset + windowCenter + Vector(0, windowSize[1])*(i-1)*difficultyButtonSpread, Vector(windowSize[0]/6, windowSize[1]/10), difficultyButtonColors, difficultyNames[iterDifficulty], difficultySettingDict[iterDifficulty]))
    difficultyHighscoreTexts.append(Text(difficultyButtonOffset + windowCenter + Vector(0, windowSize[1])*(i-1)*difficultyButtonSpread+highscoreDisplayOffset, mainFont))

customModeButton = GenericLocationButton(Vector(buttonSize*8, 17*windowSize[1]/20), Vector(windowSize[0]/6, windowSize[1]/10), customModeButtonColors, "Custom", LOC_CUSTOM_MENU)
customModeTitle = Text(Vector(windowCenter[0], windowSize[1]/9), titleFont, "Custom Mode")

exitButton = ExitButton(Vector(windowSize[0]/9, windowSize[1]/10), Vector(windowSize[0]/8, windowSize[1]/9), exitButtonColors)

imageSize = buttonSizeVector*0.7
mineImage = pg.transform.scale(pg.image.load("Assets/mine.png").convert_alpha(), (buttonSizeVector*0.9).components)
flagImage = pg.transform.scale(pg.image.load("Assets/flag.png").convert_alpha(), (buttonSizeVector*0.7).components)

field = fieldDimensions = mineAmount = None #set default value (values will be set accordingly once difficulty is selected)

playing = True
while playing:
    isNewClick = False
    screen.fill((100, 100, 100))

    for event in pg.event.get():
        if event.type == pg.QUIT:
            virtualLocation = LOC_EXIT
            playing = False
        
        if event.type == pg.MOUSEBUTTONDOWN:
            isNewClick = True
        
        if event.type == pg.KEYDOWN:
            if event.key == pg.K_d and isIngame(virtualLocation):
                deltaModeEnabled = bool((int(deltaModeEnabled)+1)%2)

    mousePos = Vector(pg.mouse.get_pos())
    islClick, isrClick = pg.mouse.get_pressed()[0], pg.mouse.get_pressed()[2] #will be true as long as the click button is held
    mouseData = (mousePos, islClick, isrClick, isNewClick)

    if virtualLocation == LOC_MAIN_MENU:
        virtualLocation, field, fieldDimensions, isTimed, mineAmount, difficulty = renderMainMenuFrame(screen, mouseData, isTimed, highscores)

    elif isIngame(virtualLocation):
        virtualLocation, field, deltaModeEnabled, highscores = renderIngameFrame(field, fieldDimensions, screen, mouseData, deltaModeButton, deltaModeEnabled, (mineAmount, mineCountCenter, mineCountColors), mainMenuButton, virtualLocation, difficulty, highscores)
        if not isIngame(virtualLocation):
            difficulty = DIFFICULTY_DEFAULT
    
    elif virtualLocation == LOC_CUSTOM_MENU:
        virtualLocation, field, fieldDimensions, mineAmount = renderCustomMenuFrame(screen, mouseData)

    elif virtualLocation == LOC_EXIT:
        playing = False
    
    pg.display.update()

pg.quit()

#update highscores to json file
with open("highscores.json", "w") as writeFile:
    json.dump(highscores, writeFile)
