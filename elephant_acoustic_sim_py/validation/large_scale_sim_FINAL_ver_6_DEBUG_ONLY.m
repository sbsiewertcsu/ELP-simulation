%
% Author: Abhirath Koushik
%
% DEBUG / BATCH MODE — No graphics, pure simulation physics
% Runs N trials per strategy and collects statistics.
%
% Metrics collected per trial:
%   1. Elephants poached (count)
%   2. Poachers neutralized (count)
%   3. Sim-time to first poach (days)
%   4. Sim-time to first neutralization (days)
%   5. Total sim-time elapsed at end of trial (days)
%
% Stop condition per trial:
%   - All elephants poached, OR
%   - All poachers neutralized, OR
%   - MAX_SIM_DAYS reached (timeout)
%
clear; clc;

% =========================================================================
% BATCH CONFIGURATION — edit these
% =========================================================================
NUM_RUNS        = 50;       % Monte Carlo trials per strategy
MIC_STRATEGY    = 1;         % 1=Uniform 2=Fortress 3=Perimeter 4=50/50
NUM_MICS        = 600;        % Number of microphones
MAX_SIM_DAYS    = 30;        % Max sim-days before trial times out
SIM_DT          = 250.0;       % Sim-seconds per physics step

% =========================================================================
% 1. CONFIGURATION & SCALING
% =========================================================================
WIDTH  = 600;
HEIGHT = 600;
SF_X   = WIDTH  / 1000;
SF_Y   = HEIGHT / 1000;
METERS_PER_PIXEL    = 158;
SPEED_ELEPHANT_MPS  = 1.11;
SPEED_POACHER_MPS   = 0.55;
SPEED_RANGER_MPS    = 5.55;
DETECTION_PROBABILITY = 0.90;
POACH_PROBABILITY     = 0.85;
SCAN_INTERVAL_SIM     = 1.0;

m2px = @(meters) meters / METERS_PER_PIXEL;

% Distances
RAD_NOLA_M    = 3040; RAD_SALO_M   = 2280; RAD_BAYANGA_M  = 3040;
RAD_LIDJOMBO_M= 2280; RAD_MOSSIPA_M= 2280;
BAI_RAD_M     = 400;  BAI_SENSE_M  = 6080;
MIC_RANGE_E_M = 3950; MIC_RANGE_P_M = 200;
POACH_DIST_M  = 100;
DIST_REACHED_M= 1266; AVOID_BUFFER_M= 2533; DEEP_FOREST_M = 10000;

MAX_SIM_TIME  = MAX_SIM_DAYS * 86400;

% Step sizes per physics iteration
step_e = (SPEED_ELEPHANT_MPS * SIM_DT) / METERS_PER_PIXEL;
step_p = (SPEED_POACHER_MPS  * SIM_DT) / METERS_PER_PIXEL;
step_r = (SPEED_RANGER_MPS   * SIM_DT) / METERS_PER_PIXEL;

strat_names = ["Uniform Spread","Targeted Fortress","Perimeter Defense","50/50 Split"];

% =========================================================================
% 2. PARK BOUNDARY
% =========================================================================
ref_poly_x = [50,150,300,450,600,680,750,850,980,980,850,720,650,620,640,620,550,500,450,380,350,350,320,250,200,100,50,20,50];
ref_poly_y = [150,100,60,50,20,20,20,30,40,120,140,140,300,400,500,650,800,900,1000,850,750,650,550,520,480,400,300,280,150];
park_boundary_x = ref_poly_x * SF_X;
park_boundary_y = ref_poly_y * SF_Y;
isInsidePark_poly = @(x,y) inpolygon(x, y, park_boundary_x, park_boundary_y);

% Pre-compute grid lookup for fast boundary checks
[grid_xx, grid_yy] = meshgrid(0:WIDTH, 0:HEIGHT);
park_grid = inpolygon(grid_xx, grid_yy, park_boundary_x, park_boundary_y);
isInsidePark = @(x,y) park_grid(min(max(round(y)+1,1),HEIGHT+1), min(max(round(x)+1,1),WIDTH+1));

% =========================================================================
% 3. ENVIRONMENT
% =========================================================================
repulsors(1) = struct('x',320*SF_X,'y',220*SF_Y,'radius',m2px(RAD_NOLA_M),   'name','Nola');
repulsors(2) = struct('x',380*SF_X,'y',430*SF_Y,'radius',m2px(RAD_SALO_M),   'name','Salo');
repulsors(3) = struct('x',480*SF_X,'y',600*SF_Y,'radius',m2px(RAD_BAYANGA_M), 'name','Bayanga');
repulsors(4) = struct('x',380*SF_X,'y',750*SF_Y,'radius',m2px(RAD_LIDJOMBO_M),'name','Lidjombo');
repulsors(5) = struct('x',190*SF_X,'y',120*SF_Y,'radius',m2px(RAD_MOSSIPA_M), 'name','Mossipa');
attractor.x = 550*SF_X; attractor.y = 550*SF_Y;
attractor.radius = m2px(BAI_RAD_M);
attractor.sensing_range = m2px(BAI_SENSE_M);
num_elephants = 20;
num_poachers  = 10;

% =========================================================================
% 4. PRE-COMPUTE POSITION POOLS (done once, reused every trial)
% =========================================================================
fprintf('Pre-computing position pools...\n');
POOL_SIZE = 2000;

pool_general = zeros(POOL_SIZE,2); count_g = 0;
for att = 1:200000
    tx=rand()*WIDTH; ty=rand()*HEIGHT;
    if isInsidePark(tx,ty) && norm([tx-attractor.x,ty-attractor.y]) > attractor.radius+m2px(AVOID_BUFFER_M)
        count_g=count_g+1; pool_general(count_g,:)=[tx,ty];
        if count_g==POOL_SIZE, break; end
    end
end
pool_general = pool_general(1:count_g,:);

pool_elephant = zeros(POOL_SIZE,2); count_e = 0;
for att = 1:200000
    tx=rand()*WIDTH; ty=rand()*HEIGHT;
    if isInsidePark(tx,ty)
        in_red=false;
        for r=1:length(repulsors)
            if norm([tx-repulsors(r).x,ty-repulsors(r).y]) < repulsors(r).radius+m2px(1266)
                in_red=true; break;
            end
        end
        if ~in_red
            count_e=count_e+1; pool_elephant(count_e,:)=[tx,ty];
            if count_e==POOL_SIZE, break; end
        end
    end
end
pool_elephant = pool_elephant(1:count_e,:);

pool_deep = zeros(POOL_SIZE,2); count_d = 0;
for att = 1:200000
    tx=rand()*WIDTH; ty=rand()*HEIGHT;
    if isInsidePark(tx,ty) && norm([tx-attractor.x,ty-attractor.y]) > m2px(DEEP_FOREST_M)
        count_d=count_d+1; pool_deep(count_d,:)=[tx,ty];
        if count_d==POOL_SIZE, break; end
    end
end
pool_deep = pool_deep(1:count_d,:);
if count_d == 0, pool_deep = pool_elephant; count_d = count_e; end

% =========================================================================
% 5. SENSOR NETWORK (placed once — same layout every trial for determinism)
% =========================================================================
mic_specs.range_e = m2px(MIC_RANGE_E_M);
mic_specs.range_p = m2px(MIC_RANGE_P_M);

fprintf('Placing microphones (Strategy %d: %s, N=%d)...\n', MIC_STRATEGY, strat_names(MIC_STRATEGY), NUM_MICS);
if MIC_STRATEGY == 1
    [mic_layout, num_mics] = place_mics_uniform(WIDTH, HEIGHT, isInsidePark, mic_specs, NUM_MICS);
elseif MIC_STRATEGY == 2
    [mic_layout, num_mics] = place_mics_fortress(WIDTH, HEIGHT, isInsidePark, mic_specs, repulsors, NUM_MICS);
elseif MIC_STRATEGY == 3
    [mic_layout, num_mics] = place_mics_perimeter(WIDTH, HEIGHT, park_boundary_x, park_boundary_y, mic_specs, NUM_MICS);
elseif MIC_STRATEGY == 4
    [mic_layout, num_mics] = place_mics_optimized_web(WIDTH, HEIGHT, isInsidePark, mic_specs, repulsors, attractor, m2px, park_boundary_x, park_boundary_y, NUM_MICS);
end

% =========================================================================
% PRINT TRIAL HEADER
% =========================================================================
fprintf('\n========================================================\n');
fprintf('  BATCH SIMULATION — DEBUG MODE\n');
fprintf('========================================================\n');
fprintf('  Strategy    : %s\n', strat_names(MIC_STRATEGY));
fprintf('  Elephants   : %d\n', num_elephants);
fprintf('  Poachers    : %d\n', num_poachers);
fprintf('  Microphones : %d (placed: %d)\n', NUM_MICS, num_mics);
fprintf('  Trials      : %d\n', NUM_RUNS);
fprintf('  Max sim-days: %d\n', MAX_SIM_DAYS);
fprintf('  SIM_DT      : %.1f sim-seconds/step\n', SIM_DT);
fprintf('  Poach prob  : %.2f  |  Detect prob: %.2f\n', POACH_PROBABILITY, DETECTION_PROBABILITY);
fprintf('========================================================\n\n');
fprintf('%-6s %-12s %-12s %-18s %-18s %-16s\n', ...
    'Trial','Poached','Neutralized','Time 1st Poach','Time 1st Neutral','Total Time');
fprintf('%s\n', repmat('-',1,84));

% =========================================================================
% RESULTS STORAGE
% =========================================================================
results = struct();
results.poached       = zeros(1, NUM_RUNS);
results.neutralized   = zeros(1, NUM_RUNS);
results.time_1st_poach  = zeros(1, NUM_RUNS);   % in sim-days, 0 = never
results.time_1st_neutral= zeros(1, NUM_RUNS);   % in sim-days, 0 = never
results.total_time    = zeros(1, NUM_RUNS);      % in sim-days

% =========================================================================
% MAIN BATCH LOOP
% =========================================================================
for run = 1:NUM_RUNS
    % --- Reset mic state (keep positions from mic_layout) ---
    mics = mic_layout;
    for m = 1:num_mics
        mics(m).elephant_memory = -999999;
        mics(m).has_memory      = false;
        mics(m).missed          = false;
        mics(m).active_e        = false;
        mics(m).active_p        = false;
        mics(m).threat          = false;
        mics(m).last_scan       = 0;
    end

    % --- Initialize elephants ---
    players = struct();
    for k = 1:num_elephants
        valid = false;
        while ~valid
            sx=rand()*WIDTH; sy=rand()*HEIGHT;
            if isInsidePark(sx,sy)
                in_red=false;
                for r=1:length(repulsors)
                    if norm([sx-repulsors(r).x,sy-repulsors(r).y])<repulsors(r).radius+m2px(1266)
                        in_red=true; break;
                    end
                end
                if ~in_red, players(k).x=sx; players(k).y=sy; valid=true; end
            end
        end
        players(k).is_poached=false; players(k).poach_time=-999;
        players(k).is_threatened=false; players(k).encounter_rolled=false;
        players(k).state="ROAMING"; players(k).attractorEntryTime=0;
        players(k).last_visit_time=-999; players(k).vx=0; players(k).vy=0;
        idx=randi(count_e);
        players(k).target_x=pool_elephant(idx,1); players(k).target_y=pool_elephant(idx,2);
    end

    % --- Initialize poachers ---
    poachers = struct();
    for p = 1:num_poachers
        valid = false;
        while ~valid
            if rand()>0.5
                sn=randi(length(repulsors));
                sx=repulsors(sn).x+(rand()-0.5)*m2px(6000);
                sy=repulsors(sn).y+(rand()-0.5)*m2px(6000);
                if isInsidePark(sx,sy) && norm([sx-attractor.x,sy-attractor.y])>attractor.radius+m2px(AVOID_BUFFER_M)
                    valid=true;
                end
            else
                ii=randi(length(park_boundary_x));
                sx=park_boundary_x(ii)+(rand()-0.5)*m2px(5000);
                sy=park_boundary_y(ii)+(rand()-0.5)*m2px(5000);
                if ~isInsidePark(sx,sy), valid=true; end
            end
        end
        poachers(p).x=sx; poachers(p).y=sy; poachers(p).vx=0; poachers(p).vy=0;
        idx=randi(count_g);
        poachers(p).target_x=pool_general(idx,1); poachers(p).target_y=pool_general(idx,2);
        poachers(p).is_caught=false; poachers(p).caught_time=-999;
        poachers(p).is_targeted=false;
        poachers(p).ranger_x=-999; poachers(p).ranger_y=-999;
        poachers(p).base_x=-999;   poachers(p).base_y=-999;
    end

    % --- Trial state ---
    current_sim_time  = 0;
    time_1st_poach    = 0;  % 0 = never occurred
    time_1st_neutral  = 0;
    first_poach_done  = false;
    first_neutral_done= false;

    % =================================================================
    % SIMULATION LOOP (no graphics)
    % =================================================================
    while current_sim_time < MAX_SIM_TIME

        current_sim_time = current_sim_time + SIM_DT;

        % --- 1. POACHER MOVEMENT ---
        for p = 1:num_poachers
            if poachers(p).is_caught, continue; end
            dist = norm([poachers(p).target_x-poachers(p).x, poachers(p).target_y-poachers(p).y]);
            if dist < m2px(DIST_REACHED_M)
                idx=randi(count_g);
                poachers(p).target_x=pool_general(idx,1); poachers(p).target_y=pool_general(idx,2);
                dist=norm([poachers(p).target_x-poachers(p).x, poachers(p).target_y-poachers(p).y]);
            end
            des_vx=(poachers(p).target_x-poachers(p).x)/dist;
            des_vy=(poachers(p).target_y-poachers(p).y)/dist;
            d_green=norm([poachers(p).x-attractor.x, poachers(p).y-attractor.y]);
            if d_green < attractor.radius+m2px(3000)
                des_vx=des_vx+((poachers(p).x-attractor.x)/d_green)*4.0;
                des_vy=des_vy+((poachers(p).y-attractor.y)/d_green)*4.0;
            end
            mag=norm([des_vx,des_vy]); if mag>0, des_vx=des_vx/mag; des_vy=des_vy/mag; end
            poachers(p).vx=poachers(p).vx*0.95+des_vx*0.05;
            poachers(p).vy=poachers(p).vy*0.95+des_vy*0.05;
            mag=norm([poachers(p).vx,poachers(p).vy]);
            if mag>0, poachers(p).vx=poachers(p).vx/mag; poachers(p).vy=poachers(p).vy/mag; end
            was_in=isInsidePark(poachers(p).x,poachers(p).y);
            nx=poachers(p).x+poachers(p).vx*step_p; ny=poachers(p).y+poachers(p).vy*step_p;
            if was_in && ~isInsidePark(nx,ny)
                poachers(p).vx=-poachers(p).vx; poachers(p).vy=-poachers(p).vy;
                idx=randi(count_g);
                poachers(p).target_x=pool_general(idx,1); poachers(p).target_y=pool_general(idx,2);
            else
                poachers(p).x=nx; poachers(p).y=ny;
            end
        end

        % --- 2. ELEPHANT MOVEMENT ---
        for k = 1:num_elephants
            if players(k).is_poached, continue; end
            dist=norm([players(k).target_x-players(k).x, players(k).target_y-players(k).y]);
            d_bai=norm([players(k).x-attractor.x, players(k).y-attractor.y]);
            if players(k).state=="ROAMING"
                if (current_sim_time-players(k).last_visit_time)>60 && d_bai<attractor.sensing_range
                    players(k).state="SEEKING";
                end
            elseif players(k).state=="SEEKING"
                if d_bai<attractor.radius
                    players(k).state="WAITING"; players(k).attractorEntryTime=current_sim_time;
                end
            elseif players(k).state=="WAITING"
                if (current_sim_time-players(k).attractorEntryTime)>10
                    players(k).state="ROAMING"; players(k).last_visit_time=current_sim_time;
                    idx=randi(count_d);
                    players(k).target_x=pool_deep(idx,1); players(k).target_y=pool_deep(idx,2);
                end
            end
            if dist<m2px(AVOID_BUFFER_M) && players(k).state~="WAITING"
                idx=randi(count_e);
                players(k).target_x=pool_elephant(idx,1); players(k).target_y=pool_elephant(idx,2);
                dist=norm([players(k).target_x-players(k).x, players(k).target_y-players(k).y]);
            end
            if players(k).state=="WAITING", des_vx=0; des_vy=0;
            else, des_vx=(players(k).target_x-players(k).x)/dist; des_vy=(players(k).target_y-players(k).y)/dist; end
            if players(k).state=="SEEKING"
                des_vx=des_vx+((attractor.x-players(k).x)/d_bai)*0.8;
                des_vy=des_vy+((attractor.y-players(k).y)/d_bai)*0.8;
            end
            for r=1:length(repulsors)
                d_rep=norm([players(k).x-repulsors(r).x, players(k).y-repulsors(r).y]);
                if d_rep<repulsors(r).radius+m2px(AVOID_BUFFER_M)
                    des_vx=des_vx+((players(k).x-repulsors(r).x)/d_rep)*4.0;
                    des_vy=des_vy+((players(k).y-repulsors(r).y)/d_rep)*4.0;
                end
            end
            mag=norm([des_vx,des_vy]); if mag>0, des_vx=des_vx/mag; des_vy=des_vy/mag; end
            players(k).vx=players(k).vx*0.95+des_vx*0.05;
            players(k).vy=players(k).vy*0.95+des_vy*0.05;
            mag=norm([players(k).vx,players(k).vy]);
            if mag>0, players(k).vx=players(k).vx/mag; players(k).vy=players(k).vy/mag; end
            nx=players(k).x+players(k).vx*step_e; ny=players(k).y+players(k).vy*step_e;
            if isInsidePark(nx,ny)
                players(k).x=nx; players(k).y=ny;
            else
                players(k).vx=-players(k).vx; players(k).vy=-players(k).vy;
                idx=randi(count_e);
                players(k).target_x=pool_elephant(idx,1); players(k).target_y=pool_elephant(idx,2);
            end
        end

        % --- 3. SENSOR NETWORK ---
        for m = 1:num_mics
            if (current_sim_time-mics(m).last_scan) >= SCAN_INTERVAL_SIM
                mics(m).last_scan=current_sim_time;
                mics(m).active_e=false; mics(m).active_p=false;
                mics(m).threat=false; mics(m).missed=false;
                e_in_range=false; p_in_range=false;
                for k=1:num_elephants
                    if players(k).is_poached, continue; end
                    if norm([players(k).x-mics(m).x, players(k).y-mics(m).y])<mic_specs.range_e
                        e_in_range=true;
                        if rand()<=DETECTION_PROBABILITY
                            mics(m).active_e=true; mics(m).elephant_memory=current_sim_time;
                        end
                    end
                end
                for p=1:num_poachers
                    if poachers(p).is_caught, continue; end
                    if norm([poachers(p).x-mics(m).x, poachers(p).y-mics(m).y])<mic_specs.range_p
                        p_in_range=true;
                        if rand()<=DETECTION_PROBABILITY, mics(m).active_p=true; end
                    end
                end
                if e_in_range||p_in_range
                    if (e_in_range&&~mics(m).active_e)||(p_in_range&&~mics(m).active_p)
                        mics(m).missed=true;
                    end
                end
                mics(m).has_memory=(current_sim_time-mics(m).elephant_memory)<=14400;
                if mics(m).active_p && (mics(m).active_e||mics(m).has_memory)
                    for p=1:num_poachers
                        if poachers(p).is_caught||poachers(p).is_targeted, continue; end
                        if norm([poachers(p).x-mics(m).x, poachers(p).y-mics(m).y])<mic_specs.range_p
                            mics(m).threat=true; poachers(p).is_targeted=true;
                            closest_dist=inf; closest_base=1;
                            for r=1:length(repulsors)
                                d=norm([poachers(p).x-repulsors(r).x, poachers(p).y-repulsors(r).y]);
                                if d<closest_dist, closest_dist=d; closest_base=r; end
                            end
                            poachers(p).base_x=repulsors(closest_base).x;
                            poachers(p).base_y=repulsors(closest_base).y;
                            poachers(p).ranger_x=poachers(p).base_x;
                            poachers(p).ranger_y=poachers(p).base_y;
                        end
                    end
                end
            end
        end

        % --- 3.5 RANGER INTERCEPTION ---
        for p = 1:num_poachers
            if poachers(p).is_targeted && ~poachers(p).is_caught
                dist=norm([poachers(p).x-poachers(p).ranger_x, poachers(p).y-poachers(p).ranger_y]);
                if dist<m2px(500)
                    poachers(p).is_caught=true; poachers(p).caught_time=current_sim_time;
                    if ~first_neutral_done
                        time_1st_neutral=current_sim_time/86400;
                        first_neutral_done=true;
                    end
                else
                    vx=(poachers(p).x-poachers(p).ranger_x)/dist;
                    vy=(poachers(p).y-poachers(p).ranger_y)/dist;
                    poachers(p).ranger_x=poachers(p).ranger_x+vx*step_r;
                    poachers(p).ranger_y=poachers(p).ranger_y+vy*step_r;
                end
            end
        end

        % --- 4. POACHING CHECK ---
        for k = 1:num_elephants
            if players(k).is_poached, continue; end
            players(k).is_threatened=false;
            elephant_in_range=false;
            for p = 1:num_poachers
                if poachers(p).is_caught, continue; end
                d_ep=norm([players(k).x-poachers(p).x, players(k).y-poachers(p).y]);
                if d_ep<m2px(POACH_DIST_M)
                    elephant_in_range=true;
                    d_safe=norm([players(k).x-attractor.x, players(k).y-attractor.y]);
                    if d_safe>attractor.radius
                        players(k).is_threatened=true;
                        if ~players(k).encounter_rolled
                            players(k).encounter_rolled=true;
                            if rand()<=POACH_PROBABILITY
                                players(k).is_poached=true;
                                players(k).poach_time=current_sim_time;
                                if ~first_poach_done
                                    time_1st_poach=current_sim_time/86400;
                                    first_poach_done=true;
                                end
                            else
                                flee_dx=players(k).x-poachers(p).x;
                                flee_dy=players(k).y-poachers(p).y;
                                flee_mag=norm([flee_dx,flee_dy]);
                                flee_dx=flee_dx/flee_mag; flee_dy=flee_dy/flee_mag;
                                flee_dist=m2px(AVOID_BUFFER_M)*1.2;
                                players(k).target_x=players(k).x+flee_dx*flee_dist;
                                players(k).target_y=players(k).y+flee_dy*flee_dist;
                                idx=randi(count_g);
                                poachers(p).target_x=pool_general(idx,1);
                                poachers(p).target_y=pool_general(idx,2);
                            end
                        end
                    end
                end
            end
            if ~elephant_in_range, players(k).encounter_rolled=false; end
        end

        % --- STOP CONDITIONS ---
        poached_now    = sum([players.is_poached]);
        caught_now     = sum([poachers.is_caught]);
        if poached_now == num_elephants || caught_now == num_poachers
            break;
        end

    end % simulation loop

    % --- Collect results ---
    poached_count    = sum([players.is_poached]);
    neutral_count    = sum([poachers.is_caught]);
    total_days       = current_sim_time / 86400;

    results.poached(run)        = poached_count;
    results.neutralized(run)    = neutral_count;
    results.time_1st_poach(run) = time_1st_poach;
    results.time_1st_neutral(run)= time_1st_neutral;
    results.total_time(run)     = total_days;

    % --- Per-trial print ---
    fp_str = '---';
    fn_str = '---';
    if first_poach_done,   fp_str = sprintf('%.2f days', time_1st_poach);   end
    if first_neutral_done, fn_str = sprintf('%.2f days', time_1st_neutral); end

    fprintf('%-6d %-12s %-12s %-18s %-18s %-16s\n', ...
        run, ...
        sprintf('%d / %d', poached_count, num_elephants), ...
        sprintf('%d / %d', neutral_count, num_poachers), ...
        fp_str, fn_str, ...
        sprintf('%.2f days', total_days));
    drawnow;

end % batch loop

% =========================================================================
% SUMMARY STATISTICS
% =========================================================================
fprintf('\n%s\n', repmat('=',1,84));
fprintf('  SUMMARY — %s  |  %d Mics  |  %d Trials\n', strat_names(MIC_STRATEGY), num_mics, NUM_RUNS);
fprintf('%s\n', repmat('=',1,84));

% Only include trials where event occurred for time metrics
valid_poach   = results.time_1st_poach(results.time_1st_poach > 0);
valid_neutral = results.time_1st_neutral(results.time_1st_neutral > 0);

fprintf('  Elephants poached    — Mean: %.1f%%  |  Std: %.1f%%  |  Min: %.0f%%  |  Max: %.0f%%\n', ...
    mean(results.poached)/num_elephants*100, std(results.poached)/num_elephants*100, ...
    min(results.poached)/num_elephants*100,  max(results.poached)/num_elephants*100);

fprintf('  Poachers neutralized — Mean: %.1f%%  |  Std: %.1f%%  |  Min: %.0f%%  |  Max: %.0f%%\n', ...
    mean(results.neutralized)/num_poachers*100, std(results.neutralized)/num_poachers*100, ...
    min(results.neutralized)/num_poachers*100,  max(results.neutralized)/num_poachers*100);

if ~isempty(valid_poach)
    fprintf('  Time to 1st poach    — Mean: %.2f days  |  Std: %.2f  |  Min: %.2f  |  Max: %.2f  (%d/%d trials)\n', ...
        mean(valid_poach), std(valid_poach), min(valid_poach), max(valid_poach), length(valid_poach), NUM_RUNS);
else
    fprintf('  Time to 1st poach    — No poaching events occurred\n');
end

if ~isempty(valid_neutral)
    fprintf('  Time to 1st neutral  — Mean: %.2f days  |  Std: %.2f  |  Min: %.2f  |  Max: %.2f  (%d/%d trials)\n', ...
        mean(valid_neutral), std(valid_neutral), min(valid_neutral), max(valid_neutral), length(valid_neutral), NUM_RUNS);
else
    fprintf('  Time to 1st neutral  — No neutralizations occurred\n');
end

fprintf('  Total sim-time       — Mean: %.2f days  |  Std: %.2f  |  Min: %.2f  |  Max: %.2f\n', ...
    mean(results.total_time), std(results.total_time), min(results.total_time), max(results.total_time));

fprintf('%s\n\n', repmat('=',1,84));

% Save results to workspace for further analysis
fprintf('Results saved to workspace variable: results\n');

% STRATEGY 1: UNIFORM GLOBAL SPREAD
function [mics, num_mics] = place_mics_uniform(WIDTH, HEIGHT, isInsidePark, mic_specs, num_mics)
    mics = repmat(struct('x',0,'y',0,'active_e',false,'active_p',false,...
        'threat',false,'last_scan',0,'missed',false,'has_memory',false), num_mics, 1);

    % ---------------------------------------------------------------
    % Step 1: Build a dense candidate grid of valid park positions
    % ---------------------------------------------------------------
    grid_step = 10; % 10px resolution — fine enough for 600x600 space
    candidates = [];
    for gx = grid_step:grid_step:WIDTH
        for gy = grid_step:grid_step:HEIGHT
            if isInsidePark(gx, gy)
                candidates(end+1, :) = [gx, gy]; 
            end
        end
    end

    if isempty(candidates)
        num_mics = 0;
        mics = mics(1:0);
        return;
    end

    n_cands = size(candidates, 1);

    % ---------------------------------------------------------------
    % Step 2: Farthest Point Sampling
    % Each new mic = candidate farthest from all placed mics
    % ---------------------------------------------------------------
    min_dists = inf(n_cands, 1); % min dist from each candidate to any placed mic

    % Seed: start from the candidate closest to the park centroid
    centroid = mean(candidates, 1);
    [~, seed_idx] = min(vecnorm(candidates - centroid, 2, 2));

    count = 1;
    mics(count).x = candidates(seed_idx, 1);
    mics(count).y = candidates(seed_idx, 2);

    % Update distances after placing seed
    min_dists = vecnorm(candidates - candidates(seed_idx, :), 2, 2);

    while count < num_mics
        % Place next mic at the candidate maximally far from all placed mics
        [~, best_idx] = max(min_dists);

        count = count + 1;
        mics(count).x = candidates(best_idx, 1);
        mics(count).y = candidates(best_idx, 2);

        % Update min distances with the newly placed mic
        d_new = vecnorm(candidates - candidates(best_idx, :), 2, 2);
        min_dists = min(min_dists, d_new);
    end

    mics = mics(1:count);
    num_mics = count;
end

% STRATEGY 2: TARGETED FORTRESS
function [mics, num_mics] = place_mics_fortress(WIDTH, HEIGHT, isInsidePark, ...
                             mic_specs, repulsors, num_mics)

    mics = repmat(struct('x',0,'y',0,'active_e',false,'active_p',false,'threat',false, ...
        'last_scan',0,'missed',false,'has_memory',false,'elephant_memory',-999999), num_mics, 1);
    count = 0;

    % --- Proportional allocation ---
    num_villages     = length(repulsors);
    budget_village   = round(num_mics * 0.75);
    mics_per_village = floor(budget_village / num_villages);

    % --- Village rings ---
    for r = 1:num_villages
        ring_radius = repulsors(r).radius + mic_specs.range_p;
        for i = 1:mics_per_village
            angle = (i / mics_per_village) * 2 * pi;
            mx = repulsors(r).x + ring_radius * cos(angle);
            my = repulsors(r).y + ring_radius * sin(angle);
            if isInsidePark(mx, my) && count < num_mics
                count = count + 1;
                mics(count).x = mx; mics(count).y = my;
            end
        end
    end

    % --- Fill remaining slots using Farthest Point Sampling ---
    % Step 1: Build dense candidate grid
    grid_step = 10;
    candidates = [];
    for gx = grid_step:grid_step:WIDTH
        for gy = grid_step:grid_step:HEIGHT
            if isInsidePark(gx, gy)
                candidates(end+1, :) = [gx, gy];
            end
        end
    end

    % Step 2: Initialise min_dists from already-placed village ring mics
    % so FPS treats them as already "occupying" space
    n_cands = size(candidates, 1);
    min_dists = inf(n_cands, 1);
    for j = 1:count
        d = vecnorm(candidates - [mics(j).x, mics(j).y], 2, 2);
        min_dists = min(min_dists, d);
    end

    % Step 3: FPS fills remaining slots
    while count < num_mics
        [~, best_idx] = max(min_dists);
        count = count + 1;
        mics(count).x = candidates(best_idx, 1);
        mics(count).y = candidates(best_idx, 2);

        % Update min distances with newly placed mic
        d_new = vecnorm(candidates - candidates(best_idx, :), 2, 2);
        min_dists = min(min_dists, d_new);
    end

    mics = mics(1:count);
    num_mics = count;
end

% STRATEGY 3: PERIMETER DEFENSE
function [mics, num_mics] = place_mics_perimeter(~, ~, park_boundary_x, park_boundary_y, mic_specs, num_mics)
    mics = repmat(struct('x',0,'y',0,'active_e',false,'active_p',false,'threat',false, ...
        'last_scan',0,'missed',false,'has_memory',false,'elephant_memory',-999999), num_mics, 1);
    count = 0;
    total_length = 0;
    for i=1:length(park_boundary_x)-1
        total_length=total_length+norm([park_boundary_x(i+1)-park_boundary_x(i),park_boundary_y(i+1)-park_boundary_y(i)]);
    end
    spacing=total_length/num_mics; curr_dist=0; segment=1;
    while count<num_mics && segment<length(park_boundary_x)
        p1=[park_boundary_x(segment),park_boundary_y(segment)];
        p2=[park_boundary_x(segment+1),park_boundary_y(segment+1)];
        seg_len=norm(p2-p1);
        while curr_dist+spacing<=seg_len && count<num_mics
            curr_dist=curr_dist+spacing;
            ratio=curr_dist/seg_len;
            mx=p1(1)+ratio*(p2(1)-p1(1)); my=p1(2)+ratio*(p2(2)-p1(2));
            dir=(p2-p1)/seg_len; normal=[-dir(2),dir(1)];
            mx=mx+normal(1)*mic_specs.range_p*0.5;
            my=my+normal(2)*mic_specs.range_p*0.5;
            count=count+1; mics(count).x=mx; mics(count).y=my;
        end
        curr_dist=curr_dist-seg_len; segment=segment+1;
    end
    mics=mics(1:count); num_mics=count;
end

% STRATEGY 4: 50/50 SPLIT
function [mics, num_mics] = place_mics_optimized_web(WIDTH, HEIGHT, isInsidePark, mic_specs, repulsors, ~, m2px, park_boundary_x, park_boundary_y, num_mics)

    mics = repmat(struct('x',0,'y',0,'active_e',false,'active_p',false,'threat',false, ...
        'last_scan',0,'missed',false,'has_memory',false,'elephant_memory',-999999), num_mics, 1);
    count = 0;

    % ---------------------------------------------------------------
    % Phase 1: 50% — Village rings (exact S2 logic)
    % ---------------------------------------------------------------
    half_mics        = floor(num_mics * 0.5);
    num_villages     = length(repulsors);
    mics_per_village = floor(half_mics / num_villages);

    for r = 1:num_villages
        ring_radius = repulsors(r).radius + mic_specs.range_p;
        for i = 1:mics_per_village
            angle = (i / mics_per_village) * 2 * pi;
            mx = repulsors(r).x + ring_radius * cos(angle);
            my = repulsors(r).y + ring_radius * sin(angle);
            if isInsidePark(mx, my) && count < half_mics
                count = count + 1;
                mics(count).x = mx;
                mics(count).y = my;
            end
        end
    end

    % ---------------------------------------------------------------
    % Phase 2: 50% — Perimeter defense (exact S3 logic)
    % ---------------------------------------------------------------
    total_length = 0;
    for i = 1:length(park_boundary_x)-1
        total_length = total_length + norm([park_boundary_x(i+1)-park_boundary_x(i), ...
                                            park_boundary_y(i+1)-park_boundary_y(i)]);
    end

    % Spacing based on remaining slots needed
    spacing = total_length / half_mics;
    curr_dist = 0;
    segment   = 1;

    while count < num_mics && segment < length(park_boundary_x)
        p1 = [park_boundary_x(segment),   park_boundary_y(segment)];
        p2 = [park_boundary_x(segment+1), park_boundary_y(segment+1)];
        seg_len = norm(p2 - p1);

        while curr_dist + spacing <= seg_len && count < num_mics
            curr_dist = curr_dist + spacing;
            ratio = curr_dist / seg_len;
            mx = p1(1) + ratio * (p2(1) - p1(1));
            my = p1(2) + ratio * (p2(2) - p1(2));

            dir    = (p2 - p1) / seg_len;
            normal = [-dir(2), dir(1)];
            mx = mx + normal(1) * (mic_specs.range_p * 0.5);
            my = my + normal(2) * (mic_specs.range_p * 0.5);

            count = count + 1;
            mics(count).x = mx;
            mics(count).y = my;
        end
        curr_dist = curr_dist - seg_len;
        segment   = segment + 1;
    end

    % ---------------------------------------------------------------
    % Phase 3: FPS fill for any remaining slots (exact S1/S2 logic)
    % ---------------------------------------------------------------
    if count < num_mics
        % Build candidate grid
        grid_step  = 10;
        candidates = [];
        for gx = grid_step:grid_step:WIDTH
            for gy = grid_step:grid_step:HEIGHT
                if isInsidePark(gx, gy)
                    candidates(end+1, :) = [gx, gy];
                end
            end
        end

        % Seed min_dists from all already-placed mics
        n_cands   = size(candidates, 1);
        min_dists = inf(n_cands, 1);
        for j = 1:count
            d = vecnorm(candidates - [mics(j).x, mics(j).y], 2, 2);
            min_dists = min(min_dists, d);
        end

        % FPS fills remaining slots
        while count < num_mics
            [~, best_idx] = max(min_dists);
            count = count + 1;
            mics(count).x = candidates(best_idx, 1);
            mics(count).y = candidates(best_idx, 2);
            d_new     = vecnorm(candidates - candidates(best_idx, :), 2, 2);
            min_dists = min(min_dists, d_new);
        end
    end

    mics     = mics(1:count);
    num_mics = count;
end
