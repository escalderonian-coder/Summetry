# blockblast_full.py
# BlockBlast-style math puzzle using pygame
# - Horizontal piece row, smaller previews, scale-up drag preview
# - Piece generator biased to produce at least one placeable piece
# - Exact-target clearing rule (TARGET_SUM == 25)
import pygame, random, sys, math, os
from time import perf_counter

# ---------------- CONFIG ----------------
GRID_SIZE = 7           # board is GRID_SIZE x GRID_SIZE
CELL = 88               # pixel size of each cell
PADDING = 18
SIDEBAR_WIDTH = 460     # wider sidebar
TARGET_SUM = 25         # exact-match rule: only equal to this clears
POINTS_PER_CELL = 15
TIMER_SECONDS = 180     # 3 minutes
CLEAR_ANIM = 0.45       # seconds for clear animation
PARTICLE_LIFE = 0.9
BEST_FILE = "best_score.txt"
FPS = 60
# ----------------------------------------

pygame.init()
# audio may fail on some systems — don't let it crash
try:
    pygame.mixer.init()
except Exception:
    pass

# --- Colors ---
WHITE = (250, 250, 250)
BG = (238, 241, 246)
CARD = (245, 247, 250)
GRID_BORDER = (200, 205, 214)
HIGHLIGHT = (100, 220, 140, 120)
BAD = (240, 120, 120, 140)
UI_TEXT = (26, 30, 35)
ACCENT = (255, 160, 50)
RED = (230, 80, 80)
GREEN = (80, 200, 120)
PURPLE = (180, 100, 220)
BLUE = (45, 130, 255)
YELLOW = (255, 220, 80)
ORANGE = (255, 150, 50)
PINK = (255, 100, 180)
TEAL = (50, 200, 200)

# Block colors
BLOCK_COLORS = [
    BLUE,           # Blue
    GREEN,          # Green  
    RED,            # Red
    YELLOW,         # Yellow
    PURPLE,         # Purple
    ORANGE,         # Orange
    PINK,           # Pink
    TEAL            # Teal
]

# Hype texts for clears
HYPE_TEXTS = ["CLEAR!", "ANGAS!", "LUPET!", "ANG GALING!", "AMAZING!", "WOW!", "INCREDIBLE!", "PERFECT!"]

# fonts (scaled up)
FONT = pygame.font.Font(None, 24)
BIG = pygame.font.Font(None, 36)
LARGE = pygame.font.Font(None, 56)
SMALL = pygame.font.Font(None, 18)

# Try to load a pixelated font, fall back to default if not available
try:
    # You can replace this with an actual pixel font file if you have one
    PIXEL_FONT = pygame.font.Font(None, 60)  # Using default for now
except:
    PIXEL_FONT = pygame.font.Font(None, 60)

# screen
WIDTH = GRID_SIZE * CELL + SIDEBAR_WIDTH + PADDING*3
HEIGHT = GRID_SIZE * CELL + PADDING*2
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("BlockBlast Math — Full Edition (Exact 25)")

clock = pygame.time.Clock()

# ---------- helper functions ----------
def clamp(a, b, c):
    return max(b, min(a, c))

def draw_text(surf, text, pos, font_obj=FONT, color=UI_TEXT, center=False):
    t = font_obj.render(text, True, color)
    r = t.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    surf.blit(t, r)

def draw_pixel_text(surf, text, pos, color=UI_TEXT, center=False):
    """Draw text with a pixelated appearance"""
    # Create a surface for the text
    text_surf = PIXEL_FONT.render(text, True, color)
    
    # Scale up then down to create pixelated effect
    scaled_up = pygame.transform.scale(text_surf, (text_surf.get_width()*2, text_surf.get_height()*2))
    pixelated = pygame.transform.scale(scaled_up, (text_surf.get_width(), text_surf.get_height()))
    
    r = pixelated.get_rect()
    if center:
        r.center = pos
    else:
        r.topleft = pos
    surf.blit(pixelated, r)

# ---------- Shapes: 1=occupied, 0=empty ----------
SHAPES = [
    [[1]],                     # single
    [[1,1]],                   # 2 hor
    [[1],[1]],                 # 2 vert
    [[1,1,1]],                 # 3 hor
    [[1],[1],[1]],             # 3 vert
    [[1,1],[1,1]],             # square 2x2
    [[1,1,1],[0,1,0]],         # T
    [[1,1],[1,0]],             # L
    [[1,1],[0,1]],             # reverse L
    [[1,0],[1,0],[1,1]],       # L tall
    [[0,1],[0,1],[1,1]],       # reversed tall L
    [[1,0,1],[1,1,1]],         # U-ish
    [[1,1,1,1]],               # 4 horizontal
    [[1],[1,1],[1]],           # plus-ish
]

def random_piece_from_shape(shape=None, bias='neutral'):
    """
    Fill a shape's occupied cells with integers:
      bias == 'low'  -> numbers from 1..3
      bias == 'high' -> numbers from 3..5
      bias == 'neutral' -> numbers from 1..5
    """
    if shape is None:
        shape = random.choice(SHAPES)
    if bias == 'low':
        mn, mx = 1, 3
    elif bias == 'high':
        mn, mx = 3, 5
    else:
        mn, mx = 1, 5
    return [[(random.randint(mn, mx) if cell==1 else 0) for cell in row] for row in shape]

class Piece:
    def __init__(self, shape=None, bias='neutral'):
        # allow shape to be a raw shape (list of lists with 1/0) or a full-numbered shape
        if shape is None:
            self.shape = random_piece_from_shape(None, bias)
        else:
            # detect whether shape contains numbers already (non-0 and >1) or just 1s
            contains_numbers = any(any(cell not in (0,1) for cell in row) for row in shape)
            if contains_numbers:
                self.shape = shape
            else:
                # shape is a template of 1/0; fill numbers with bias
                self.shape = random_piece_from_shape(shape, bias)
        self.h = len(self.shape)
        self.w = len(self.shape[0])
        # Assign a random color to this piece
        self.color = random.choice(BLOCK_COLORS)

    def rotated(self):
        new = [list(row) for row in zip(*self.shape[::-1])]
        p = Piece.__new__(Piece)
        p.shape = new
        p.h = len(new)
        p.w = len(new[0])
        p.color = self.color  # Keep the same color when rotating
        return p

# ---------- Particle for nice effects ----------
class Particle:
    def __init__(self, x, y, color, life=PARTICLE_LIFE):
        self.x = x; self.y = y
        self.vx = random.uniform(-80, 80)
        self.vy = random.uniform(-180, -30)
        self.color = color
        self.life = life
        self.birth = perf_counter()

    def age(self):
        return perf_counter() - self.birth

    def alive(self):
        return self.age() < self.life

    def draw(self, surf):
        t = self.age() / self.life
        alpha = int(255 * (1 - t))
        r = int(6 * (1 - t) + 1)
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, self.color + (alpha,), (r, r), r)
        surf.blit(s, (self.x - r, self.y - r))
    
    def update(self, dt):
        self.vy += 400 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

# ---------- Score popup ----------
class Popup:
    def __init__(self, x, y, text, dur=1.0):
        self.x = x; self.y = y; self.text = text; self.start = perf_counter(); self.dur = dur

    def alive(self):
        return perf_counter() - self.start < self.dur

    def draw(self, surf):
        t = perf_counter() - self.start
        a = clamp(1 - t/self.dur, 0, 1)
        txt = FONT.render(self.text, True, UI_TEXT)
        txt.set_alpha(int(255*a))
        surf.blit(txt, (self.x, self.y - t*28))

# ---------- Hype Text Popup ----------
class HypePopup:
    def __init__(self, x, y, text, dur=0.7):
        self.x = x; self.y = y; self.text = text; self.start = perf_counter(); self.dur = dur

    def alive(self):
        return perf_counter() - self.start < self.dur

    def draw(self, surf):
        t = perf_counter() - self.start
        # Fade in for first half, fade out for second half
        if t < self.dur/2:
            a = t / (self.dur/2)  # Fade in: 0 to 1
        else:
            a = 1 - (t - self.dur/2) / (self.dur/2)  # Fade out: 1 to 0
            
        a = clamp(a, 0, 1)
        # Use a larger font for hype text
        txt = LARGE.render(self.text, True, random.choice(BLOCK_COLORS))
        txt.set_alpha(int(255*a))
        r = txt.get_rect(center=(self.x, self.y))
        surf.blit(txt, r)

# ---------- Menu class ----------
class Menu:
    def __init__(self):
        self.active = True
        self.timed_mode = True
        self.showing_credits = False
        self.showing_mechanics = False
        self.buttons = [
            {"rect": pygame.Rect(WIDTH//2 - 100, HEIGHT//2 - 40, 200, 50), "text": "TIMED MODE", "action": "timed"},
            {"rect": pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 20, 200, 50), "text": "RELAXED MODE", "action": "relaxed"},
            {"rect": pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 80, 200, 50), "text": "CREDITS", "action": "credits"},
            {"rect": pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 140, 200, 50), "text": "MECHANICS", "action": "mechanics"}
        ]
        self.back_button = pygame.Rect(WIDTH//2 - 100, HEIGHT - 80, 200, 50)
        
        # Scroll mechanics
        self.mechanics_scroll = 0
        self.max_mechanics_scroll = 0
    
    def draw(self):
        screen.fill(BG)
        
        if self.showing_credits:
            self.draw_credits()
        elif self.showing_mechanics:
            self.draw_mechanics()
        else:
            self.draw_main_menu()
    
    def draw_main_menu(self):
        # Title with pixelated font
        draw_pixel_text(screen, "SUMMETRY", (WIDTH//2, HEIGHT//3), UI_TEXT, center=True)
        
        # Buttons
        for button in self.buttons:
            color = GREEN if (button["action"] == "timed" and self.timed_mode) or (button["action"] == "relaxed" and not self.timed_mode) else CARD
            if button["action"] == "credits":
                color = PURPLE
            elif button["action"] == "mechanics":
                color = TEAL
            pygame.draw.rect(screen, color, button["rect"], border_radius=12)
            pygame.draw.rect(screen, GRID_BORDER, button["rect"], 2, border_radius=12)
            draw_text(screen, button["text"], button["rect"].center, BIG, UI_TEXT, center=True)
        
        # Instructions
        draw_text(screen, "Click a piece then place it on the board", (WIDTH//2, HEIGHT - 100), FONT, UI_TEXT, center=True)
        draw_text(screen, "Press P to pause", (WIDTH//2, HEIGHT - 70), FONT, UI_TEXT, center=True)
    
    def draw_credits(self):
        # Title with pixelated font
        draw_pixel_text(screen, "CREDITS", (WIDTH//2, HEIGHT//4), UI_TEXT, center=True)
        
        # Credits text with cute formatting
        credits_lines = [
            "🎉 This program and math puzzle was lovingly",
            "created by Ian alongside David! :3",
            "",
            "We really appreciate you playing and hope",
            "you had fun solving it!",
            "",
            "For feedback, suggestions, or just to say hi,",
            "you can reach us through our Facebook accounts",
            "or via the Google Docs attached to this game.",
            "",
            "Thank you so much for playing, and...",
            "an Advanced Merry Christmas! 🎄✨"
        ]
        
        y_pos = HEIGHT//3
        for line in credits_lines:
            if line:  # Only draw non-empty lines
                draw_text(screen, line, (WIDTH//2, y_pos), FONT, UI_TEXT, center=True)
            y_pos += 30
        
        # Back button
        pygame.draw.rect(screen, ACCENT, self.back_button, border_radius=12)
        pygame.draw.rect(screen, GRID_BORDER, self.back_button, 2, border_radius=12)
        draw_text(screen, "BACK", self.back_button.center, BIG, UI_TEXT, center=True)
    
    def draw_mechanics(self):
        # Title with pixelated font
        draw_pixel_text(screen, "GAME MECHANICS", (WIDTH//2, HEIGHT//8), UI_TEXT, center=True)
        
        # Mechanics text - FIXED: "OBJECTIVES" is now properly visible
        mechanics_lines = [
            "🎯 OBJECTIVES:",
            "Complete rows or columns that sum to exactly 25",
            "",
            "🧩 HOW TO PLAY:",
            "- Click on a piece from the sidebar",
            "- Drag and place it on the board",
            "- Complete rows/columns to clear them",
            "- Each cleared cell gives you 15 points",
            "",
            "⏰ TIMED MODE:",
            "- You have 3 minutes to score as many points as possible",
            "- Race against the clock!",
            "- Game ends when time runs out or no moves left",
            "",
            "🌙 RELAXED MODE:",
            "- No time limit, play at your own pace",
            "- Perfect for learning the game mechanics",
            "- Game only ends when no moves are left",
            "",
            "🎮 CONTROLS:",
            "- P: Pause/Resume the game",
            "- ESC: Return to main menu",
            "- Mouse Wheel: Scroll this menu",
            "",
            "💥 SPECIAL FEATURES:",
            "- Colorful blocks for visual appeal",
            "- Hype text appears when clearing rows/columns",
            "- Restart and Quit buttons during gameplay",
            "- Best score tracking",
            "",
            "💡 TIPS:",
            "- Plan your moves to complete multiple lines at once",
            "- Balance speed with strategy in Timed Mode",
            "- Watch for pieces that can help complete multiple lines"
        ]
        
        # Calculate total height needed
        total_height = len(mechanics_lines) * 30
        self.max_mechanics_scroll = max(0, total_height - HEIGHT * 0.7)
        
        # Apply scroll
        y_pos = HEIGHT//6 - self.mechanics_scroll
        
        # Create a clipping area for the scrollable content
        scroll_area = pygame.Rect(WIDTH//2 - 300, HEIGHT//6, 600, HEIGHT * 0.6)
        screen.set_clip(scroll_area)
        
        for line in mechanics_lines:
            if line:  # Only draw non-empty lines
                # Check if line is within visible area
                if scroll_area.top <= y_pos <= scroll_area.bottom:
                    draw_text(screen, line, (WIDTH//2, y_pos), FONT, UI_TEXT, center=True)
            y_pos += 30
        
        # Reset clipping
        screen.set_clip(None)
        
        # Draw scroll indicator if needed
        if self.max_mechanics_scroll > 0:
            # Calculate scroll bar position
            scroll_ratio = self.mechanics_scroll / self.max_mechanics_scroll
            scroll_bar_height = 200
            scroll_bar_y = HEIGHT//6 + (HEIGHT * 0.6 - scroll_bar_height) * scroll_ratio
            
            # Draw scroll bar background
            pygame.draw.rect(screen, GRID_BORDER, (WIDTH//2 + 280, HEIGHT//6, 10, HEIGHT * 0.6), border_radius=5)
            # Draw scroll bar thumb
            pygame.draw.rect(screen, ACCENT, (WIDTH//2 + 280, scroll_bar_y, 10, scroll_bar_height), border_radius=5)
        
        # Back button
        pygame.draw.rect(screen, ACCENT, self.back_button, border_radius=12)
        pygame.draw.rect(screen, GRID_BORDER, self.back_button, 2, border_radius=12)
        draw_text(screen, "BACK", self.back_button.center, BIG, UI_TEXT, center=True)
    
    def handle_click(self, mx, my):
        if self.showing_credits or self.showing_mechanics:
            if self.back_button.collidepoint(mx, my):
                self.showing_credits = False
                self.showing_mechanics = False
                return False
        else:
            for button in self.buttons:
                if button["rect"].collidepoint(mx, my):
                    if button["action"] == "timed":
                        self.timed_mode = True
                        self.active = False
                        return True
                    elif button["action"] == "relaxed":
                        self.timed_mode = False
                        self.active = False
                        return True
                    elif button["action"] == "credits":
                        self.showing_credits = True
                        return False
                    elif button["action"] == "mechanics":
                        self.showing_mechanics = True
                        self.mechanics_scroll = 0  # Reset scroll when opening
                        return False
        return False
    
    def handle_scroll(self, dy):
        if self.showing_mechanics:
            self.mechanics_scroll = clamp(self.mechanics_scroll + dy * 30, 0, self.max_mechanics_scroll)

# ---------- Game class ----------
class BlockBlastGame:
    def __init__(self, timed_mode=True):
        self.board_size = GRID_SIZE
        self.cell = CELL
        self.side_w = SIDEBAR_WIDTH
        self.grid = [[0]*self.board_size for _ in range(self.board_size)]
        self.grid_nums = [[0]*self.board_size for _ in range(self.board_size)]
        self.grid_colors = [[None]*self.board_size for _ in range(self.board_size)]  # Store colors for each cell
        
        # Initialize tracking variables for piece generation
        self.last_piece_time = perf_counter()
        self.consecutive_single_5s = 0  # Track consecutive single 5s
        
        # Generate initial pieces
        self.pieces = [self.generate_placeable_piece() for _ in range(3)]
        self.selected = None          # index of selected piece
        self.dragging = False         # true if piece is grabbed and moving with mouse
        self.score = 0
        self.best = self.load_best()
        self.game_over = False
        self.start_time = perf_counter()
        self.particles = []
        self.popups = []
        self.hype_popups = []  # New list for hype text popups
        self.animations = []
        self.paused = False
        self.timed_mode = timed_mode

        # geometry
        self.board_rect = pygame.Rect(PADDING, PADDING, self.board_size*self.cell, self.board_size*self.cell)
        self.sidebar_rect = pygame.Rect(self.board_rect.right + PADDING, PADDING, self.side_w, self.board_rect.h)
        # three piece slots horizontally higher (moved up to avoid overlapping controls)
        self.slot_area = pygame.Rect(self.sidebar_rect.left + 20, self.sidebar_rect.top + 240, self.sidebar_rect.width - 40, 120)
        
        # Button areas for restart and quit
        button_width = (self.sidebar_rect.width - 60) // 2
        self.restart_button = pygame.Rect(self.sidebar_rect.left + 20, self.sidebar_rect.bottom - 70, button_width, 50)
        self.quit_button = pygame.Rect(self.sidebar_rect.left + 40 + button_width, self.sidebar_rect.bottom - 70, button_width, 50)

    def load_best(self):
        try:
            if os.path.exists(BEST_FILE):
                with open(BEST_FILE, "r") as f:
                    return int(f.read().strip() or "0")
        except Exception:
            pass
        return 0

    def save_best(self):
        try:
            with open(BEST_FILE, "w") as f:
                f.write(str(self.best))
        except Exception:
            pass

    # --- helpers for adaptive generation ---
    def board_average(self):
        vals = []
        for r in range(self.board_size):
            for c in range(self.board_size):
                v = self.grid_nums[r][c]
                if v != 0:
                    vals.append(v)
        if not vals:
            return None
        return sum(vals)/len(vals)

    def choose_bias_from_board(self):
        avg = self.board_average()
        if avg is None:
            return 'neutral'
        if avg >= 3.5:
            return 'low'
        if avg <= 2.0:
            return 'high'
        return 'neutral'

    def find_near_lines_and_needed(self, max_empty=3):
        candidates = []
        # rows
        for y in range(self.board_size):
            empties = []
            s = 0
            for x in range(self.board_size):
                if self.grid[y][x] == 0:
                    empties.append(x)
                else:
                    s += self.grid_nums[y][x]
            if 1 <= len(empties) <= max_empty:
                needed_total = TARGET_SUM - s
                mn = 1 * len(empties)
                mx = 5 * len(empties)
                if mn <= needed_total <= mx:
                    candidates.append(("row", y, empties, needed_total))
        # cols
        for x in range(self.board_size):
            empties = []
            s = 0
            for y in range(self.board_size):
                if self.grid[y][x] == 0:
                    empties.append(y)
                else:
                    s += self.grid_nums[y][x]
            if 1 <= len(empties) <= max_empty:
                needed_total = TARGET_SUM - s
                mn = 1 * len(empties)
                mx = 5 * len(empties)
                if mn <= needed_total <= mx:
                    candidates.append(("col", x, empties, needed_total))
        return candidates

    def generate_placeable_piece(self, tries=150):
        # Check if we've been generating too many single 5s
        current_time = perf_counter()
        time_since_last = current_time - self.last_piece_time
        
        # Reset counter if it's been a while since last piece
        if time_since_last > 5.0:
            self.consecutive_single_5s = 0
        
        # First try to generate a useful piece for near-complete lines (but not too aggressively)
        # Only try strategic generation 30% of the time to avoid spoonfeeding
        if random.random() < 0.3:
            candidates = self.find_near_lines_and_needed(max_empty=3)
            random.shuffle(candidates)
            for kind, idx, empties, needed_total in candidates:
                for shape in SHAPES:
                    shape_h = len(shape)
                    shape_w = len(shape[0])
                    if kind == "row":
                        y = idx
                        for top in range(max(0, y-shape_h+1), min(self.board_size-shape_h, y)+1):
                            for left in range(0, self.board_size-shape_w+1):
                                positions = []
                                for dy in range(shape_h):
                                    for dx in range(shape_w):
                                        if shape[dy][dx] == 1:
                                            gx = left + dx
                                            gy = top + dy
                                            if gy == y and gx in empties:
                                                positions.append((gx, gy))
                                            else:
                                                if not (0 <= gx < self.board_size and 0 <= gy < self.board_size):
                                                    positions = None
                                                    break
                                                if self.grid[gy][gx] != 0:
                                                    positions = None
                                                    break
                                    if positions is None:
                                        break
                                if not positions:
                                    continue
                                occ_cells = [(left+dx, top+dy) for dy in range(shape_h) for dx in range(shape_w) if shape[dy][dx]==1]
                                row_indices = [i for i,p in enumerate(occ_cells) if p[1]==y and p[0] in empties]
                                if not row_indices:
                                    continue
                                def compositions(total, k, mn=1, mx=5):
                                    if k == 1:
                                        if mn <= total <= mx:
                                            yield (total,)
                                        return
                                    for v in range(mn, mx+1):
                                        for rest in compositions(total-v, k-1, mn, mx):
                                            yield (v,) + rest
                                for parts in compositions(needed_total, len(row_indices), 1, 5):
                                    shape_numbers = {}
                                    for idx_i, pval in zip(row_indices, parts):
                                        gx, gy = occ_cells[idx_i]
                                        sx = gx - left
                                        sy = gy - top
                                        shape_numbers[(sy, sx)] = pval
                                    bias = self.choose_bias_from_board()
                                    mn, mx = (1,3) if bias=='low' else ((3,5) if bias=='high' else (1,5))
                                    full_shape = []
                                    for dy in range(shape_h):
                                        row_vals = []
                                        for dx in range(shape_w):
                                            if shape[dy][dx]==1:
                                                if (dy,dx) in shape_numbers:
                                                    row_vals.append(shape_numbers[(dy,dx)])
                                                else:
                                                    row_vals.append(random.randint(mn, mx))
                                            else:
                                                row_vals.append(0)
                                        full_shape.append(row_vals)
                                    candidate = Piece(full_shape)
                                    if self.can_place(candidate, left, top):
                                        self.last_piece_time = current_time
                                        return candidate
                                # fixed indentation below:
                                for try_sum in range(needed_total-1, max(0, needed_total - 6)-1, -1):
                                    if not (1*len(row_indices) <= try_sum <= 5*len(row_indices)):
                                        continue
                                    for parts in compositions(try_sum, len(row_indices), 1, 5):
                                        shape_numbers = {}
                                        for idx_i, pval in zip(row_indices, parts):
                                            gx, gy = occ_cells[idx_i]
                                            sx = gx - left
                                            sy = gy - top
                                            shape_numbers[(sy, sx)] = pval
                                        bias = self.choose_bias_from_board()
                                        mn, mx = (1,3) if bias=='low' else ((3,5) if bias=='high' else (1,5))
                                        full_shape = []
                                        for dy in range(shape_h):
                                            row_vals = []
                                            for dx in range(shape_w):
                                                if shape[dy][dx]==1:
                                                    if (dy,dx) in shape_numbers:
                                                        row_vals.append(shape_numbers[(dy,dx)])
                                                    else:
                                                        row_vals.append(random.randint(mn, mx))
                                                else:
                                                    row_vals.append(0)
                                            full_shape.append(row_vals)
                                        candidate = Piece(full_shape)
                                        if self.can_place(candidate, left, top):
                                            self.last_piece_time = current_time
                                            return candidate
        
        # If no strategic piece found, generate a random one with variety
        free_cells = sum(1 for r in range(self.board_size) for c in range(self.board_size) if self.grid[r][c] == 0)
        small_shapes = [s for s in SHAPES if sum(sum(row) for row in s) <= 2]
        medium_shapes = [s for s in SHAPES if 3 <= sum(sum(row) for row in s) <= 4]
        large_shapes = [s for s in SHAPES if sum(sum(row) for row in s) >= 4]
        bias = self.choose_bias_from_board()
        
        for _ in range(tries):
            if free_cells <= 10:
                shape = random.choice(small_shapes + medium_shapes)
            elif free_cells <= 20:
                shape = random.choice(medium_shapes + small_shapes + large_shapes)
            else:
                shape = random.choice(SHAPES)
            
            # Avoid single 5 pieces if we've had too many recently
            if len(shape) == 1 and len(shape[0]) == 1 and self.consecutive_single_5s >= 2:
                shape = random.choice([s for s in SHAPES if sum(sum(row) for row in s) > 1])
            
            p = Piece(shape, bias)
            
            # Track consecutive single 5s
            if len(p.shape) == 1 and len(p.shape[0]) == 1 and p.shape[0][0] == 5:
                self.consecutive_single_5s += 1
            else:
                self.consecutive_single_5s = 0
            
            if self.find_any_pos(p):
                self.last_piece_time = current_time
                return p
        
        # Final fallback - ensure variety
        shapes_with_variety = [s for s in SHAPES if sum(sum(row) for row in s) > 1]
        if shapes_with_variety:
            p = Piece(random.choice(shapes_with_variety), bias)
            if self.find_any_pos(p):
                self.last_piece_time = current_time
                return p
        
        # Absolute fallback
        p = Piece([[1, 1]], bias)
        self.last_piece_time = current_time
        return p

    def any_move_possible(self):
        for piece in self.pieces:
            if self.find_any_pos(piece):
                return True
        return False

    def find_any_pos(self, piece):
        for y in range(self.board_size - piece.h + 1):
            for x in range(self.board_size - piece.w + 1):
                if self.can_place(piece, x, y):
                    return (x, y)
        return None

    def can_place(self, piece, x, y):
        for dy in range(piece.h):
            for dx in range(piece.w):
                if piece.shape[dy][dx] != 0:
                    gx, gy = x+dx, y+dy
                    if gx < 0 or gx >= self.board_size or gy < 0 or gy >= self.board_size:
                        return False
                    if self.grid[gy][gx] != 0:
                        return False
        return True

    def place_piece(self, idx, piece, x, y):
        # REMOVED: No longer saving snapshot for undo functionality
        for dy in range(piece.h):
            for dx in range(piece.w):
                if piece.shape[dy][dx] != 0:
                    self.grid[y+dy][x+dx] = 1
                    self.grid_nums[y+dy][x+dx] = piece.shape[dy][dx]
                    self.grid_colors[y+dy][x+dx] = piece.color  # Store the color
        
        # FIXED: Only replace the used piece, keep the other two
        self.pieces[idx] = self.generate_placeable_piece()
        
        cleared_cells, points = self.check_and_animate()
        if points > 0:
            self.popups.append(Popup(self.sidebar_rect.left + 20, 40, f"+{points}"))
        if self.score > self.best:
            self.best = self.score
            self.save_best()
        if not self.any_move_possible():
            self.game_over = True

    def check_and_animate(self):
        to_clear = set()
        for y in range(self.board_size):
            if all(self.grid[y][x]!=0 for x in range(self.board_size)):
                s = sum(self.grid_nums[y])
                if s == TARGET_SUM:
                    for x in range(self.board_size):
                        to_clear.add((x,y))
        for x in range(self.board_size):
            if all(self.grid[y][x]!=0 for y in range(self.board_size)):
                s = sum(self.grid_nums[y][x] for y in range(self.board_size))
                if s == TARGET_SUM:
                    for y in range(self.board_size):
                        to_clear.add((x,y))
        if to_clear:
            self.animations.append({"cells": list(to_clear), "start": perf_counter()})
            
            # Add hype text popup
            hype_text = random.choice(HYPE_TEXTS)
            center_x = self.board_rect.left + self.board_rect.width // 2
            center_y = self.board_rect.top + self.board_rect.height // 2
            self.hype_popups.append(HypePopup(center_x, center_y, hype_text))
            
        pts = len(to_clear) * POINTS_PER_CELL
        self.score += pts
        return len(to_clear), pts

    def update_animations(self):
        now = perf_counter()
        done_anims = []
        for anim in self.animations:
            t = now - anim["start"]
            if t > CLEAR_ANIM:
                for (x,y) in anim["cells"]:
                    if self.grid[y][x] != 0:
                        color = self.grid_colors[y][x] if self.grid_colors[y][x] else (200, 200, 255)
                        for _ in range(8):
                            px = self.board_rect.left + x*self.cell + self.cell/2
                            py = self.board_rect.top + y*self.cell + self.cell/2
                            self.particles.append(Particle(px, py, color))
                        self.grid[y][x] = 0
                        self.grid_nums[y][x] = 0
                        self.grid_colors[y][x] = None
                done_anims.append(anim)
        for d in done_anims:
            self.animations.remove(d)
        
        # Update hype popups
        self.hype_popups = [hp for hp in self.hype_popups if hp.alive()]

    def draw_grid(self):
        pygame.draw.rect(screen, WHITE, self.board_rect, border_radius=12)
        for y in range(self.board_size):
            for x in range(self.board_size):
                rect = pygame.Rect(self.board_rect.left + x*self.cell, self.board_rect.top + y*self.cell, self.cell, self.cell)
                pygame.draw.rect(screen, GRID_BORDER, rect, 1)
                val = self.grid_nums[y][x]
                if self.grid[y][x]!=0:
                    # Use the stored color for the block, or default to blue if none
                    color = self.grid_colors[y][x] if self.grid_colors[y][x] else BLUE
                    r = pygame.Rect(rect.x+4, rect.y+4, rect.w-8, rect.h-8)
                    pygame.draw.rect(screen, color, r, border_radius=8)
                    draw_text(screen, str(val), r.center, BIG, WHITE, center=True)
        pygame.draw.rect(screen, GRID_BORDER, self.board_rect, 3, border_radius=12)

    def draw_sidebar(self):
        pygame.draw.rect(screen, CARD, self.sidebar_rect, border_radius=12)
        draw_text(screen, "SCORE", (self.sidebar_rect.left+20, 30), FONT)
        draw_text(screen, str(self.score), (self.sidebar_rect.left+20, 60), LARGE)
        draw_text(screen, f"BEST: {self.best}", (self.sidebar_rect.left+20, 110), FONT)
        
        if self.timed_mode:
            remain = max(0, int(TIMER_SECONDS - (perf_counter() - self.start_time)))
            draw_text(screen, f"TIME: {remain}s", (self.sidebar_rect.left+20, 140), FONT)
        else:
            elapsed = int(perf_counter() - self.start_time)
            draw_text(screen, f"TIME: {elapsed}s", (self.sidebar_rect.left+20, 140), FONT)
            
        draw_text(screen, f"TARGET = {TARGET_SUM}", (self.sidebar_rect.left+20, 170), FONT)
        pygame.draw.line(screen, GRID_BORDER, (self.sidebar_rect.left+15, self.sidebar_rect.top+210), (self.sidebar_rect.right-15, self.sidebar_rect.top+210), 1)
        draw_text(screen, "PIECES:", (self.sidebar_rect.left+20, self.sidebar_rect.top+220), FONT)
        slot_w = self.slot_area.width//3
        for i,p in enumerate(self.pieces):
            cx = self.slot_area.left + slot_w*i + slot_w/2
            cy = self.slot_area.centery
            self.draw_piece(p, cx, cy, scale=0.7, transparency=(150 if self.dragging and self.selected==i else 255))
        
        # Draw restart and quit buttons
        pygame.draw.rect(screen, GREEN, self.restart_button, border_radius=8)
        pygame.draw.rect(screen, RED, self.quit_button, border_radius=8)
        draw_text(screen, "RESTART", self.restart_button.center, FONT, WHITE, center=True)
        draw_text(screen, "QUIT", self.quit_button.center, FONT, WHITE, center=True)
        
        pygame.draw.rect(screen, GRID_BORDER, self.sidebar_rect, 3, border_radius=12)

    def draw_piece(self, piece, cx, cy, scale=1.0, transparency=255):
        sz = int(self.cell*0.7*scale)
        ph = piece.h
        pw = piece.w
        total_w = pw*sz
        total_h = ph*sz
        ox = cx - total_w/2
        oy = cy - total_h/2
        for dy in range(ph):
            for dx in range(pw):
                v = piece.shape[dy][dx]
                if v!=0:
                    rect = pygame.Rect(ox + dx*sz, oy + dy*sz, sz-6, sz-6)
                    s = pygame.Surface(rect.size, pygame.SRCALPHA)
                    # Use the piece's color
                    color = piece.color if piece.color else BLUE
                    s.fill(color + (transparency,))
                    screen.blit(s, rect.topleft)
                    draw_text(screen, str(v), rect.center, FONT, WHITE, center=True)

    def draw_particles(self, dt):
        newp = []
        for p in self.particles:
            p.update(dt)
            if p.alive():
                p.draw(screen)
                newp.append(p)
        self.particles = newp

    def draw_popups(self):
        self.popups = [pp for pp in self.popups if pp.alive()]
        for pp in self.popups:
            pp.draw(screen)
        
        # Draw hype popups
        for hp in self.hype_popups:
            hp.draw(screen)

    # --- NEW helper: draw placement preview (minimal, non-intrusive) ---
    def draw_placement_preview(self):
        if not (self.dragging and self.selected is not None):
            return
        piece = self.pieces[self.selected]
        mx, my = pygame.mouse.get_pos()
        gx = (mx - self.board_rect.left) // self.cell
        gy = (my - self.board_rect.top) // self.cell
        # valid placement check (can_place will return False if out-of-bounds or overlaps)
        valid = self.can_place(piece, gx, gy)
        # greenish for valid, reddish for invalid, with low alpha
        color = (100, 220, 140, 100) if valid else (240, 120, 120, 100)
        for dy in range(piece.h):
            for dx in range(piece.w):
                if piece.shape[dy][dx] != 0:
                    cx = gx + dx
                    cy = gy + dy
                    if 0 <= cx < self.board_size and 0 <= cy < self.board_size:
                        rect = pygame.Rect(
                            self.board_rect.left + cx*self.cell + 4,
                            self.board_rect.top + cy*self.cell + 4,
                            self.cell - 8,
                            self.cell - 8
                        )
                        s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                        s.fill(color)
                        screen.blit(s, rect.topleft)

    def handle_click(self, mx, my):
        if self.game_over:
            # Instead of resetting, we'll return to menu (handled in main loop)
            return "menu"
        if self.paused:
            return
        
        # Check if restart button was clicked
        if self.restart_button.collidepoint(mx, my):
            self.reset()
            return
        
        # Check if quit button was clicked
        if self.quit_button.collidepoint(mx, my):
            return "menu"
            
        if self.board_rect.collidepoint(mx, my):
            if self.dragging and self.selected is not None:
                piece = self.pieces[self.selected]
                gx = (mx - self.board_rect.left)//self.cell
                gy = (my - self.board_rect.top)//self.cell
                if self.can_place(piece, gx, gy):
                    self.place_piece(self.selected, piece, gx, gy)
                self.dragging = False
                self.selected = None
        else:
            slot_w = self.slot_area.width//3
            for i in range(3):
                sx = self.slot_area.left + slot_w*i
                sy = self.slot_area.top
                rect = pygame.Rect(sx, sy, slot_w, self.slot_area.height)
                if rect.collidepoint(mx, my):
                    self.selected = i
                    self.dragging = True
                    break

    def reset(self):
        self.grid = [[0]*self.board_size for _ in range(self.board_size)]
        self.grid_nums = [[0]*self.board_size for _ in range(self.board_size)]
        self.grid_colors = [[None]*self.board_size for _ in range(self.board_size)]
        self.pieces = [self.generate_placeable_piece() for _ in range(3)]
        self.selected = None
        self.dragging = False
        self.score = 0
        self.game_over = False
        self.start_time = perf_counter()
        self.particles = []
        self.popups = []
        self.hype_popups = []
        self.animations = []
        self.paused = False
        self.consecutive_single_5s = 0

    def update(self, dt):
        if not self.paused and not self.game_over:
            self.update_animations()
            if self.timed_mode and perf_counter() - self.start_time > TIMER_SECONDS:
                self.game_over = True

    def draw_gameover(self):
        s = pygame.Surface((self.board_rect.w, self.board_rect.h), pygame.SRCALPHA)
        s.fill((255,255,255,200))
        screen.blit(s, self.board_rect.topleft)
        draw_text(screen, "GAME OVER", self.board_rect.center, LARGE, RED, center=True)
        draw_text(screen, "Press Anywhere to Return to Menu", (self.board_rect.centerx, self.board_rect.centery+50), FONT, UI_TEXT, center=True)

    def draw_paused(self):
        s = pygame.Surface((self.board_rect.w, self.board_rect.h), pygame.SRCALPHA)
        s.fill((255,255,255,200))
        screen.blit(s, self.board_rect.topleft)
        draw_text(screen, "PAUSED", self.board_rect.center, LARGE, ACCENT, center=True)

    def draw(self, dt):
        screen.fill(BG)
        self.draw_grid()
        self.draw_sidebar()
        self.draw_particles(dt)
        self.draw_popups()
        if self.game_over:
            self.draw_gameover()
        elif self.paused:
            self.draw_paused()
        # show placement preview while dragging (non-intrusive)
        self.draw_placement_preview()
        if self.dragging and self.selected is not None:
            mx,my = pygame.mouse.get_pos()
            self.draw_piece(self.pieces[self.selected], mx, my, scale=1.1, transparency=200)
        pygame.display.flip()

# ----------- main ------------
def main():
    menu = Menu()
    game = None
    
    running = True
    while running:
        dt = clock.tick(FPS)/1000.0
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button==1:
                mx,my = event.pos
                if menu.active:
                    if menu.handle_click(mx, my):
                        # Create the game with the selected mode
                        game = BlockBlastGame(timed_mode=menu.timed_mode)
                elif game:
                    result = game.handle_click(mx, my)
                    if result == "menu":
                        menu.active = True
                        game = None
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game and not menu.active:
                        menu.active = True
                        game = None
                elif game and not menu.active:
                    # REMOVED: Undo functionality (U key)
                    if event.key == pygame.K_p:
                        game.paused = not game.paused
            elif event.type == pygame.MOUSEWHEEL:
                # Handle scrolling in mechanics menu
                if menu.active and menu.showing_mechanics:
                    menu.handle_scroll(event.y)
        
        if menu.active:
            menu.draw()
        elif game:
            game.update(dt)
            game.draw(dt)
            
        pygame.display.flip()
        
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()