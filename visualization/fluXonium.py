import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.transforms as transforms
import numpy as np

# ==============================================================================
# CLASS 1: THE XMON (The Cross + Pads)
# ==============================================================================
class Xmon:
    def __init__(self, arm_len=220, arm_width=30, pad_head_size=80):
        self.arm_len = arm_len
        self.arm_width = arm_width
        self.pad_head_size = pad_head_size
        self.patches = []
        self._generate_geometry()

    def _generate_geometry(self):
        c_half = self.arm_width / 2
        
        # 1. Center Square (Stored as tuple)
        center_rect = patches.Rectangle((-c_half, -c_half), self.arm_width, self.arm_width)
        self.patches.append((center_rect, 0)) 
        
        # 2. Arms & Pads
        arm_rect = (c_half, -c_half, self.arm_len, self.arm_width)
        pad_x = c_half + self.arm_len
        pad_rect = (pad_x, -self.pad_head_size/2, self.pad_head_size/1.5, self.pad_head_size)

        for angle in [0, 90, 180, 270]:
            r = patches.Rectangle((arm_rect[0], arm_rect[1]), arm_rect[2], arm_rect[3])
            self._add_rotated_patch(r, angle)
            p = patches.Rectangle((pad_rect[0], pad_rect[1]), pad_rect[2], pad_rect[3])
            self._add_rotated_patch(p, angle)

    def _add_rotated_patch(self, patch, angle_deg):
        self.patches.append((patch, angle_deg))

    def place(self, ax, xy, angle_global=0, color='#9EAAB2'):
        base_trans = transforms.Affine2D().rotate_deg(angle_global).translate(xy[0], xy[1]) + ax.transData
        for (patch_obj, local_angle) in self.patches:
            if isinstance(patch_obj, patches.Rectangle):
                new_patch = patches.Rectangle(
                    patch_obj.get_xy(), patch_obj.get_width(), patch_obj.get_height(),
                    facecolor=color, edgecolor=None
                )
                final_trans = transforms.Affine2D().rotate_deg(local_angle) + base_trans
                new_patch.set_transform(final_trans)
                ax.add_patch(new_patch)

# ==============================================================================
# CLASS 2: THE FLUXONIUM CHAIN
# ==============================================================================
class FluxoniumChain:
    def __init__(self, length, width=10, island_len=14, gap=8, overlap=3):
        self.length = length
        self.width = width
        self.island_len = island_len
        self.gap = gap
        self.overlap = overlap
        self.patches_base = []
        self.patches_bridge = []
        self._generate_local_geometry()

    def _generate_local_geometry(self):
        unit_len = self.island_len + self.gap
        num_cells = int(self.length / unit_len)
        bridge_len = self.gap + (2 * self.overlap)
        current_x = 0
        
        for i in range(num_cells + 1):
            # Base Island
            self.patches_base.append(
                (current_x, -self.width/2, self.island_len, self.width)
            )
            # Bridge
            if i < num_cells:
                bridge_x = (current_x + self.island_len) - self.overlap
                bridge_w = self.width * 0.85
                self.patches_bridge.append(
                    (bridge_x, -bridge_w/2, bridge_len, bridge_w)
                )
            current_x += unit_len
        self.final_x = current_x - unit_len + self.island_len 

    def place(self, ax, xy, angle_deg, color_base='#6B8E9B', color_top='#4A6C6F'):
        base_trans = transforms.Affine2D().rotate_deg(angle_deg).translate(xy[0], xy[1]) + ax.transData
        
        for (bx, by, bw, bh) in self.patches_base:
            r = patches.Rectangle((bx, by), bw, bh, facecolor=color_base, edgecolor=None)
            r.set_transform(base_trans)
            ax.add_patch(r)
        
        for (bx, by, bw, bh) in self.patches_bridge:
            r = patches.Rectangle((bx, by), bw, bh, facecolor=color_top, alpha=0.9, edgecolor=None)
            r.set_transform(base_trans)
            ax.add_patch(r)
            
        return self.final_x 

# ==============================================================================
# MAIN DRAWING ROUTINE
# ==============================================================================
def draw_xmon_diagonal_fluxonium_fixed():
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_aspect('equal')
    ax.set_facecolor('#F5F5F7')
    
    # 1. Place Xmon
    my_xmon = Xmon(arm_len=180, arm_width=30, pad_head_size=70)
    my_xmon.place(ax, (0,0))
    
    # 2. Setup Fluxonium Parameters
    chain_len = 220
    separation = 30  
    angle = -45      
    
    # --- POSITION FIX ---
    # Moved start_dist closer (28 instead of 40) so the first island
    # overlaps the Xmon body naturally.
    start_dist = 28
    
    rad = np.radians(angle)
    vec_fwd = np.array([np.cos(rad), np.sin(rad)])
    vec_perp = np.array([-np.sin(rad), np.cos(rad)]) 
    
    center_start = np.array([0,0]) + (vec_fwd * start_dist)
    
    start_A = center_start + (vec_perp * (separation/2))
    start_B = center_start - (vec_perp * (separation/2))
    
    # 3. Place Chains (No manual leads needed now)
    chain_def = FluxoniumChain(length=chain_len, width=10)
    actual_len = chain_def.place(ax, start_A, angle)
    chain_def.place(ax, start_B, angle)
    
    # 4. Phase Slip Loop (End)
    end_A = start_A + (vec_fwd * actual_len)
    end_B = start_B + (vec_fwd * actual_len)
    
    bar_center = (end_A + end_B) / 2
    bar_len = separation + 10 
    
    # Connector Bar
    rect_bar = patches.Rectangle((-bar_len/2, -5), bar_len, 10, facecolor='#6B8E9B')
    trans_bar = transforms.Affine2D().rotate_deg(angle + 90).translate(bar_center[0], bar_center[1]) + ax.transData
    rect_bar.set_transform(trans_bar)
    ax.add_patch(rect_bar)
    
    # Phase Slip Junction
    rect_jj = patches.Rectangle((-5, -8), 10, 16, facecolor='#D95F5F', zorder=10)
    trans_jj = transforms.Affine2D().rotate_deg(angle).translate(bar_center[0], bar_center[1]) + ax.transData
    rect_jj.set_transform(trans_jj)
    ax.add_patch(rect_jj)

    # View
    ax.set_xlim(-250, 250)
    ax.set_ylim(-250, 250)
    ax.axis('off')

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    draw_xmon_diagonal_fluxonium_fixed()