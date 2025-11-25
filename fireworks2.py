import pygame
import json
import random
import math
import os

# Список ярких цветов для взрывов фейерверков
VIBRANT_COLORS = [
    (255, 80, 80), (255, 180, 60), (255, 255, 120),
    (120, 255, 120), (120, 255, 255), (100, 180, 255),
    (160, 120, 255), (255, 120, 255), (255, 150, 200),
]

# Глобальные переменные (будут заполнены после инициализации микшера)
EXPLOSION_SOUNDS = []
WIND_SOUND = None
wind_playing = False


class Particle:
    # Класс отдельной искры после взрыва фейерверка
    def __init__(self, x, y, color, gravity, lifespan, fade_speed, spread, power=1.0):
        self.x = x + random.uniform(-10, 10)           # начальная позиция с небольшим разбросом
        self.y = y + random.uniform(-10, 10)           # разброс по вертикали
        self.color = color                             # цвет частицы
        angle = random.uniform(0, 2 * math.pi)         # случайный угол вылета
        speed = random.uniform(9, 17) * spread * power # начальная скорость
        self.vx = math.cos(angle) * speed              # горизонтальная скорость
        self.vy = math.sin(angle) * speed              # вертикальная скорость
        self.gravity = gravity                         # сила гравитации
        self.lifespan = lifespan                       # максимальное время жизни
        self.age = 0                                   # текущий возраст частицы
        self.alpha = 255                               # начальная непрозрачность
        self.fade_speed = fade_speed                   # скорость угасания
        self.fall_mode = False                         # режим падения (после половины жизни)
        self.drag = 0.95                               # сопротивление воздуха
        self.trail = []                                # координаты для отрисовки следа

    def update(self, wind_force):
        # Обновление физики частицы каждый кадр (с учётом ветра)
        self.age += 1
        if self.age > self.lifespan * 0.48:            # переключаемся в режим падения
            self.fall_mode = True

        self.vx += wind_force                          # ветер постоянно толкает частицу по горизонтали

        if self.fall_mode:
            self.vx *= 0.965                           # торможение по горизонтали в режиме падения
            self.vy += self.gravity * 2.8              # ускоренное падение вниз
            self.alpha = max(0, self.alpha - 2.8)      # быстрое угасание в конце жизни
        else:
            self.vy += self.gravity                    # обычное влияние гравитации
            self.vx *= self.drag                       # сопротивление воздуха по горизонтали
            self.vy *= self.drag                       # сопротивление воздуха по вертикали
            self.alpha = max(0, self.alpha - self.fade_speed)

        self.x += self.vx                              # перемещение по оси X
        self.y += self.vy                              # перемещение по оси Y
        self.trail.append((self.x, self.y, self.alpha))
        if len(self.trail) > 28:                       # ограничиваем длину следа (экономим память)
            self.trail.pop(0)

    def draw(self, screen):
        # Отрисовка следа частицы
        for i, (tx, ty, ta) in enumerate(self.trail):
            alpha = int(ta * (i / len(self.trail)) ** 1.3)
            if alpha <= 8: continue
            size = max(2, int(7 * (i / len(self.trail))))
            s = pygame.Surface((size * 2 + 6, size * 2 + 6), pygame.SRCALPHA)
            s.set_alpha(alpha)
            pygame.draw.circle(s, self.color, (size + 3, size + 3), size)
            screen.blit(s, (tx - size - 3, ty - size - 3))

        # Отрисовка самой искры с эффектом свечения
        if self.alpha > 10:
            s = pygame.Surface((28, 28), pygame.SRCALPHA)
            s.set_alpha(min(255, self.alpha))
            pygame.draw.circle(s, (*self.color, int(self.alpha * 0.5)), (14, 14), 12)  # полупрозрачный ореол
            pygame.draw.circle(s, self.color, (14, 14), 8)                           # основной круг
            bright = tuple(min(255, c + 120) for c in self.color)                    # яркая сердцевина
            pygame.draw.circle(s, bright, (14, 14), 4)
            screen.blit(s, (self.x - 14, self.y - 14))

    def is_dead(self):
        # полностью исчезла ли частица
        return self.alpha <= 0


class Firework:
    # Класс одной ракеты: подъём → взрыв → искры
    def __init__(self, width, height, cfg, instant_explosion=False):
        self.width = width
        self.height = height
        self.cfg = cfg
        self.gravity = cfg["gravity"]
        self.particles = []
        self.exploded = False
        if instant_explosion:
            self.x = width
            self.y = height
            self.explode()
        else:
            self.x = random.randint(200, width - 200)
            self.y = height
            self.vy = random.uniform(cfg["firework_min_speed"], cfg["firework_max_speed"])

    def update(self, wind_force):
        # Обновление состояния ракеты или её осколков
        if not self.exploded:
            self.y += self.vy
            self.vy += 0.18
            if self.vy >= -1.5:
                self.explode()
        else:
            for p in self.particles[:]:
                p.update(wind_force)
                if p.is_dead():
                    self.particles.remove(p)

    def explode(self):
        # Создание множества искр при взрыве
        self.exploded = True
        color = random.choice(VIBRANT_COLORS)
        count = random.randint(self.cfg["particle_count_min"], self.cfg["particle_count_max"])
        power = 1.3

        # Звук взрыва
        if EXPLOSION_SOUNDS:
            sound = random.choice(EXPLOSION_SOUNDS)
            sound.play()

        for _ in range(count):
            self.particles.append(Particle(
                self.x, self.y, color,
                self.gravity,
                self.cfg["particle_lifespan"],
                self.cfg["fade_speed"],
                self.cfg["particle_spread"],
                power
            ))

    def draw(self, screen):
        # Отрисовка ракеты до взрыва или искр после
        if not self.exploded:
            pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y)), 5)
            for i in range(8):
                py = self.y + i * 10
                if py > self.height: continue
                alpha = int(255 * (1 - i / 8))
                s = pygame.Surface((12, 12), pygame.SRCALPHA)
                s.set_alpha(alpha)
                pygame.draw.circle(s, (255, 180, 80), (6, 6), 5 - i * 0.6)
                screen.blit(s, (self.x - 6, py))
        else:
            for p in self.particles:
                p.draw(screen)

    def is_done(self):
        # можно ли удалить фейерверк из списка
        return self.exploded and len(self.particles) == 0


class WindParticle:
    # Полоска, показывающая направление и силу ветра
    def __init__(self, screen_width, screen_height):
        self.sw = screen_width
        self.sh = screen_height
        self.side = random.choice(["left", "right"])
        if self.side == "left":
            self.x = random.uniform(-600, -150)
        else:
            self.x = random.uniform(screen_width + 150, screen_width + 600)
        self.y = random.uniform(80, screen_height - 80)
        self.length = random.uniform(180, 380)
        self.thickness = random.uniform(0.4, 1.2)
        self.speed = random.uniform(3.0, 6.0)
        self.alpha = random.randint(50, 130)

    def update(self, wind_force):
        # Движение полоски с учётом силы ветра
        move_speed = self.speed + abs(wind_force) * 300
        self.x += wind_force * move_speed
        if abs(wind_force) > 0.02:
            self.alpha = min(200, self.alpha + 3.0)
        else:
            self.alpha = max(30, self.alpha - 1.5)
        if self.x < -1000 or self.x > self.sw + 1000:
            return False
        return True

    def draw(self, screen, wind_force):
        # Отрисовка полоски ветра
        if self.alpha < 20: return
        angle = 0.0
        if wind_force > 0.05: angle = -0.08
        elif wind_force < -0.05: angle = 0.08
        points = 22
        surf = pygame.Surface((int(self.length * 4), 100), pygame.SRCALPHA)
        for i in range(points):
            t = i / (points - 1)
            alpha_val = int(self.alpha * (1 - t * 0.6))
            width = int(self.thickness * (1.0 + t * 2.5))
            color = (255, 255, 255, max(0, min(255, alpha_val)))
            dx = self.length * t
            dy = math.sin(angle * 3.14) * 12 * t
            start = (surf.get_width() // 2, 50)
            end = (start[0] + dx, start[1] + dy)
            pygame.draw.line(surf, color, start, end, width)
        screen.blit(surf, (self.x - surf.get_width() // 2, self.y - 50))


class Simulation:
    # Основной класс - управляет всей симуляцией
    def __init__(self):
        # Инициализация звука ПЕРЕД pygame.init()
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.mixer.init()
        except:
            print("Звук не удалось инициализировать")

        # Загрузка звуков взрывов и ветра только после инициализации микшера
        global EXPLOSION_SOUNDS, WIND_SOUND
        for i in range(1, 6):
            for ext in [".wav", ".ogg", ".mp3"]:
                path = f"boom{i}{ext}"
                if os.path.exists(path):
                    try:
                        snd = pygame.mixer.Sound(path)
                        snd.set_volume(0.45)
                        EXPLOSION_SOUNDS.append(snd)
                        break
                    except: pass
        if os.path.exists("wind.wav"):
            WIND_SOUND = pygame.mixer.Sound("wind.wav")
        elif os.path.exists("wind.ogg"):
            WIND_SOUND = pygame.mixer.Sound("wind.ogg")

        # Параметры по умолчанию
        self.default_cfg = {
            "gravity": 0.09, "particle_lifespan": 75, "particle_count_min": 60,
            "particle_count_max": 80, "particle_spread": 0.75, "fade_speed": 4,
            "firework_spawn_rate": 0.02, "firework_min_speed": -15,
            "firework_max_speed": -13, "wind_force": 0.0
        }
        self.cfg = self.default_cfg.copy()

        # Загрузка конфига
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content: self.cfg.update(json.loads(content))
        except: pass

        pygame.init()
        self.screen = pygame.display.set_mode((1600, 900))
        pygame.display.set_caption("Фейерверки")
        self.clock = pygame.time.Clock()
        self.fireworks = []
        self.wind_particles = []
        self.running = True
        self.paused = False
        self.manual_mode = False
        self.font = pygame.font.SysFont("consolas", 16, bold=True)
        self.hud_cache = None
        self.hud_version = 0
        self.current_version = 0

        for _ in range(42):
            self.wind_particles.append(WindParticle(1600, 900))

    def reset_to_default(self):
        self.cfg = self.default_cfg.copy()
        self.fireworks.clear()
        self.wind_particles.clear()
        for _ in range(42):
            self.wind_particles.append(WindParticle(1600, 900))
        self.current_version += 1
        global wind_playing
        if wind_playing and WIND_SOUND:
            WIND_SOUND.stop()
            wind_playing = False

    def handle_keys(self):
        keys = pygame.key.get_pressed()
        changed = False
        if keys[pygame.K_g]: self.cfg["gravity"] += 0.02; changed = True
        if keys[pygame.K_b]: self.cfg["gravity"] -= 0.02; changed = True
        if keys[pygame.K_UP]:   self.cfg["firework_min_speed"] -= 0.5; self.cfg["firework_max_speed"] -= 0.5; changed = True
        if keys[pygame.K_DOWN]: self.cfg["firework_min_speed"] += 0.5; self.cfg["firework_max_speed"] += 0.5; changed = True
        if keys[pygame.K_q]: self.cfg["firework_spawn_rate"] += 0.002; changed = True
        if keys[pygame.K_e]: self.cfg["firework_spawn_rate"] -= 0.002; changed = True
        if keys[pygame.K_r]: self.cfg["particle_spread"] += 0.03; changed = True
        if keys[pygame.K_f]: self.cfg["particle_spread"] -= 0.03; changed = True
        if keys[pygame.K_PAGEUP]:   self.cfg["particle_count_min"] += 3; self.cfg["particle_count_max"] += 6; changed = True
        if keys[pygame.K_PAGEDOWN]: self.cfg["particle_count_min"] -= 3; self.cfg["particle_count_max"] -= 6; changed = True
        if keys[pygame.K_n]: self.cfg["wind_force"] -= 0.01; changed = True
        if keys[pygame.K_m]: self.cfg["wind_force"] += 0.01; changed = True

        if changed:
            self.cfg["gravity"] = max(0.01, min(0.5, self.cfg["gravity"]))
            self.cfg["firework_spawn_rate"] = max(0.001, min(0.2, self.cfg["firework_spawn_rate"]))
            self.cfg["particle_spread"] = max(0.3, min(2.5, self.cfg["particle_spread"]))
            self.cfg["particle_count_min"] = max(20, self.cfg["particle_count_min"])
            self.cfg["particle_count_max"] = max(self.cfg["particle_count_min"] + 10, self.cfg["particle_count_max"])
            self.cfg["wind_force"] = max(-0.6, min(0.6, self.cfg["wind_force"]))
            self.current_version += 1

    def run(self):
        global wind_playing
        try:
            while self.running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_SPACE:
                            self.paused = not self.paused
                            self.current_version += 1
                        if event.key == pygame.K_ESCAPE:
                            self.reset_to_default()
                        if event.key == pygame.K_RETURN:
                            self.manual_mode = not self.manual_mode
                            self.current_version += 1
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.manual_mode and not self.paused:
                            mx, my = event.pos
                            self.fireworks.append(Firework(mx, my, self.cfg, instant_explosion=True))

                if not self.paused:
                    self.handle_keys()
                    wind = self.cfg["wind_force"]

                    # Звук ветра: включается при любой силе ветра, выключается при нуле
                    if abs(wind) > 0.01 and WIND_SOUND and not wind_playing:
                        WIND_SOUND.play(loops=-1)
                        wind_playing = True
                    elif abs(wind) <= 0.01 and WIND_SOUND and wind_playing:
                        WIND_SOUND.stop()
                        wind_playing = False

                    for wp in self.wind_particles[:]:
                        if not wp.update(wind):
                            self.wind_particles.remove(wp)
                            self.wind_particles.append(WindParticle(1600, 900))

                    if not self.manual_mode:
                        if random.random() < self.cfg["firework_spawn_rate"]:
                            self.fireworks.append(Firework(1600, 900, self.cfg))

                    for fw in self.fireworks[:]:
                        fw.update(wind)
                        if fw.is_done():
                            self.fireworks.remove(fw)

                self.screen.fill((5, 5, 25))
                for wp in self.wind_particles:
                    wp.draw(self.screen, wind)
                for fw in self.fireworks:
                    fw.draw(self.screen)
                self.draw_hud()
                pygame.display.flip()
                self.clock.tick(60)

        finally:
            pygame.mixer.quit()
            pygame.quit()
            print("   мы счiтаем это максiмальный балл".center(56))

    def draw_hud(self):
        if self.hud_version != self.current_version or self.hud_cache is None:
            self.hud_version = self.current_version
            overlay = pygame.Surface((420, 520), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 185))
            wind_text = f"Ветер: {self.cfg['wind_force']:+.3f}"
            if self.cfg['wind_force'] > 0: wind_text += " →→→"
            elif self.cfg['wind_force'] < 0: wind_text += " ←←←"
            else: wind_text += " —"
            lines = [
                ("УПРАВЛЕНИЕ", (255,255,140)), ("",None),
                ("SPACE — пауза", (180,255,180)),
                ("ENTER — ручной режим " + ("ВКЛ" if self.manual_mode else "ВЫКЛ"), (255,220,100)),
                ("ESC   — сброс", (255,160,160)), ("",None),
                ("G/B      → гравитация", (220,220,255)),
                ("↑/↓      → скорость ракет", (220,220,255)),
                ("Q/E      → частота", (220,220,255)),
                ("R/F      → разброс искр", (220,220,255)),
                ("PgUp/Dn  → кол-во искр", (220,220,255)),
                ("N/M      → ветер + звук", (200,240,255)), ("",None),
                ("В ручном: ЛКМ — взрыв", (200,255,200)), ("",None),
                ("ПАРАМЕТРЫ", (255,220,100)), ("",None),
                (f"Гравитация:     {self.cfg['gravity']:.3f}", (255,240,160)),
                (f"Скорость:       {self.cfg['firework_min_speed']:.1f}..{self.cfg['firework_max_speed']:.1f}", (255,240,160)),
                (f"Частота:        {self.cfg['firework_spawn_rate']:.4f}", (255,240,160)),
                (f"Искр:           {self.cfg['particle_count_min']}–{self.cfg['particle_count_max']}", (255,240,160)),
                (f"Разброс:        {self.cfg['particle_spread']:.3f}", (255,240,160)),
                (wind_text, (200,255,255)),
            ]
            y = 18
            for text, color in lines:
                if not text: y += 10; continue
                surf = self.font.render(text, True, color)
                overlay.blit(surf, (20, y))
                y += 24
            if self.paused:
                pause = self.font.render("ПАУЗА", True, (255,80,80))
                overlay.blit(pause, (20, 480))
            self.hud_cache = overlay
        self.screen.blit(self.hud_cache, (10, 10))


if __name__ == "__main__":
    Simulation().run()