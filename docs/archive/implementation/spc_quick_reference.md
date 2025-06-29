# SPC Quick Reference Guide for SMT Current Testing

## What is SPC?
Statistical Process Control (SPC) uses control charts to monitor your process and detect problems before they cause defects.

## Key Terms
- **UCL**: Upper Control Limit - Maximum expected value for a stable process
- **LCL**: Lower Control Limit - Minimum expected value for a stable process  
- **CL**: Center Line - Average value
- **Subgroup**: Small sample of consecutive measurements (typically 5)
- **Derived Specs**: Specification limits calculated from process data when no engineering specs exist
- **X-bar Chart**: Shows average of each subgroup (monitors process center)
- **R Chart**: Shows range of each subgroup (monitors process variation)

## Control Chart Interpretation

### Good (In Control)
- All points between UCL and LCL
- Random pattern around center line
- No trends or patterns

### Bad (Out of Control) 
- ❌ Any point outside UCL or LCL
- ❌ 9 points in a row on same side of center line
- ❌ 6 points in a row going up or down
- ❌ Unusual patterns (cycles, trends)

## Using the SPC System

### Daily Operation

1. **Check SPC Tab** 
   - Green status = Process OK
   - Orange status = Still collecting data
   - Red status = Out of control

2. **During Testing**
   - System automatically collects measurements
   - No extra steps needed
   - Data saved for analysis

3. **If Out of Control**
   - Note which board/function failed
   - Check recent changes (new reel, temperature, etc.)
   - Notify engineer
   - Do NOT adjust limits yourself

### Reading the Display

```
X̄ Control Chart
UCL: 2.0847  <-- Upper limit
CL:  2.0000  <-- Target 
LCL: 1.9153  <-- Lower limit

Current Status:
Subgroups: 25/20 ✓
Last Update: 2:34 PM
Status: Ready
```

## Common Issues

### "Need more subgroups"
- Keep running normal production
- System needs 20+ subgroups minimum
- Each subgroup = 5 tests

### Point outside limits
- Does NOT mean part is bad (spec limits still apply)
- Means process changed - investigate why
- Common causes:
  - New material lot
  - Environmental change
  - Equipment drift

### All points near center line
- Too good to be true!
- Check measurement system
- May indicate gauge problem

## Process Capability

- **Cpk > 1.67**: Excellent 🟢
- **Cpk 1.33-1.67**: Good 🟡
- **Cpk 1.00-1.33**: Marginal 🟠
- **Cpk < 1.00**: Poor 🔴

## Best Practices

1. **Don't Panic** - One out-of-control point doesn't mean disaster
2. **Look for Patterns** - Single points less important than trends
3. **Document Changes** - Note any process adjustments
4. **Trust the System** - Based on YOUR actual data
5. **Ask Questions** - Engineers want to help

## SPC vs Specification Limits

| Type | Purpose | Example | Action if Exceeded |
|------|---------|---------|-------------------|
| Spec Limits | Part requirements | 1.8-2.3A | Part fails |
| Control Limits | Process monitoring | 1.92-2.08A | Investigate process |

**Remember**: Control limits are usually INSIDE spec limits. This gives early warning.

## Quick Actions

### Before Starting Shift
1. Check SPC status in GUI
2. Note any overnight alerts
3. Verify correct mode (Sampling/Production)

### During Production
1. Monitor for out-of-control alerts
2. Document any process changes
3. Investigate patterns

### End of Shift
1. Review day's control charts
2. Note any concerns for next shift
3. Export report if requested

## Contact for Help

- **SPC Questions**: Quality Engineering
- **System Issues**: Test Engineering  
- **Limit Changes**: Process Engineering

---

**Remember**: SPC helps us make better products by catching problems early. 
It's not about finding fault - it's about continuous improvement!
