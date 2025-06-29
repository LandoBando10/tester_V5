"""
Specification Deriver for SPC System
Calculates specification limits based on process capability when no engineering specs exist
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
import logging

from .spc_config import (
    TARGET_CAPABILITY, 
    SPEC_SIGMA_MULTIPLIER,
    SPEC_MARGIN_FACTOR,
    CONTROL_CONSTANTS,
    SUBGROUP_SIZE
)

logger = logging.getLogger(__name__)


@dataclass
class DerivedSpecs:
    """Derived specification limits"""
    lsl: float
    usl: float
    target: float
    process_sigma: float
    expected_cp: float
    expected_cpk: float


class SpecDeriver:
    """
    Derives specification limits from process data to achieve target capability
    
    When no engineering specifications exist, this class calculates appropriate
    specification limits based on actual process performance to achieve a 
    target Cp value (default 1.33).
    """
    
    def __init__(self, target_cp: float = TARGET_CAPABILITY):
        self.target_cp = target_cp
        
    def derive_specs(self, 
                    x_bar_bar: float, 
                    r_bar: float,
                    subgroup_size: int = SUBGROUP_SIZE) -> DerivedSpecs:
        """
        Derive specification limits from process statistics
        
        Args:
            x_bar_bar: Mean of subgroup means (process center)
            r_bar: Mean of subgroup ranges
            subgroup_size: Size of each subgroup
            
        Returns:
            DerivedSpecs object with calculated limits
        """
        # Get d2 constant for sigma estimation
        if subgroup_size not in CONTROL_CONSTANTS:
            raise ValueError(f"No constants available for subgroup size {subgroup_size}")
            
        d2 = CONTROL_CONSTANTS[subgroup_size]['d2']
        
        # Estimate process sigma from average range
        sigma_within = r_bar / d2
        
        # Calculate specification width for target Cp
        # Cp = (USL - LSL) / (6 * sigma)
        # Therefore: (USL - LSL) = Cp * 6 * sigma
        spec_width = self.target_cp * 6 * sigma_within
        
        # For symmetric specs around the mean:
        # LSL = mean - (spec_width / 2)
        # USL = mean + (spec_width / 2)
        # This gives us Cp = Cpk = target_cp when process is centered
        
        # Using the 4-sigma approach for Cp=1.33:
        # spec_width = 8*sigma, so Cp = 8*sigma/(6*sigma) = 1.33
        half_width = SPEC_SIGMA_MULTIPLIER * sigma_within * SPEC_MARGIN_FACTOR
        
        lsl = x_bar_bar - half_width
        usl = x_bar_bar + half_width
        
        # Calculate expected capability indices
        expected_cp = (usl - lsl) / (6 * sigma_within)
        
        # Since we're centering specs on the process mean, Cpk = Cp
        expected_cpk = expected_cp
        
        logger.info(f"Derived specs: LSL={lsl:.3f}, USL={usl:.3f}, "
                   f"Target={x_bar_bar:.3f}, Sigma={sigma_within:.3f}, "
                   f"Expected Cp/Cpk={expected_cp:.2f}")
        
        return DerivedSpecs(
            lsl=lsl,
            usl=usl,
            target=x_bar_bar,
            process_sigma=sigma_within,
            expected_cp=expected_cp,
            expected_cpk=expected_cpk
        )
    
    def derive_specs_from_data(self, subgroups: list) -> Optional[DerivedSpecs]:
        """
        Derive specs directly from subgroup data
        
        Args:
            subgroups: List of subgroups (each subgroup is a list of measurements)
            
        Returns:
            DerivedSpecs object or None if insufficient data
        """
        if not subgroups or len(subgroups) < 2:
            logger.warning(f"Insufficient subgroups for spec derivation: {len(subgroups) if subgroups else 0} subgroups")
            return None
            
        try:
            # Check for variable-length subgroups
            subgroup_lengths = [len(sg) for sg in subgroups]
            if len(set(subgroup_lengths)) > 1:
                logger.warning(f"Variable subgroup sizes detected: {subgroup_lengths}. Using most common size.")
                # Use the most common subgroup size
                from collections import Counter
                most_common_size = Counter(subgroup_lengths).most_common(1)[0][0]
                # Filter to only subgroups of the most common size
                subgroups = [sg for sg in subgroups if len(sg) == most_common_size]
                logger.info(f"Filtered to {len(subgroups)} subgroups of size {most_common_size}")
            
            # Convert to numpy for easier calculation
            subgroups_array = np.array(subgroups)
            logger.info(f"Processing {len(subgroups)} subgroups with shape {subgroups_array.shape}")
            
            # Calculate statistics
            subgroup_means = np.mean(subgroups_array, axis=1)
            subgroup_ranges = np.ptp(subgroups_array, axis=1)  # ptp = peak-to-peak (max-min)
            
            x_bar_bar = np.mean(subgroup_means)
            r_bar = np.mean(subgroup_ranges)
            
            subgroup_size = subgroups_array.shape[1]
            
            return self.derive_specs(x_bar_bar, r_bar, subgroup_size)
        except Exception as e:
            logger.error(f"Error in derive_specs_from_data: {e}")
            logger.error(f"Subgroups structure: {subgroups[:2] if subgroups else 'None'}")  # Log first 2 subgroups for debugging
            return None
    
    def update_specs_for_drift(self, 
                              current_specs: DerivedSpecs,
                              new_x_bar_bar: float,
                              new_r_bar: float,
                              subgroup_size: int = SUBGROUP_SIZE,
                              max_shift_percent: float = 10.0) -> DerivedSpecs:
        """
        Update derived specs when process has drifted
        
        Allows specs to follow process drift within limits to maintain
        capability while preventing excessive changes.
        
        Args:
            current_specs: Current specification limits
            new_x_bar_bar: New process center
            new_r_bar: New average range
            subgroup_size: Size of subgroups
            max_shift_percent: Maximum allowed shift as percentage of spec width
            
        Returns:
            Updated DerivedSpecs object
        """
        # Calculate new natural specs
        new_specs = self.derive_specs(new_x_bar_bar, new_r_bar, subgroup_size)
        
        # Calculate allowed shift
        current_width = current_specs.usl - current_specs.lsl
        max_shift = current_width * (max_shift_percent / 100.0)
        
        # Limit the shift in specs
        center_shift = new_specs.target - current_specs.target
        if abs(center_shift) > max_shift:
            center_shift = max_shift if center_shift > 0 else -max_shift
            
        # Apply limited shift
        adjusted_lsl = current_specs.lsl + center_shift
        adjusted_usl = current_specs.usl + center_shift
        
        # Recalculate capability with adjusted specs
        d2 = CONTROL_CONSTANTS[subgroup_size]['d2']
        sigma_within = new_r_bar / d2
        adjusted_cp = (adjusted_usl - adjusted_lsl) / (6 * sigma_within)
        
        # Calculate Cpk with new center
        cpu = (adjusted_usl - new_x_bar_bar) / (3 * sigma_within)
        cpl = (new_x_bar_bar - adjusted_lsl) / (3 * sigma_within)
        adjusted_cpk = min(cpu, cpl)
        
        logger.info(f"Updated specs with {center_shift:.3f} shift: "
                   f"LSL={adjusted_lsl:.3f}, USL={adjusted_usl:.3f}")
        
        return DerivedSpecs(
            lsl=adjusted_lsl,
            usl=adjusted_usl,
            target=new_x_bar_bar,
            process_sigma=sigma_within,
            expected_cp=adjusted_cp,
            expected_cpk=adjusted_cpk
        )