import time
import jax
import jax.numpy as jnp
import flax.serialization
from luxai_s3.params import EnvParams
from luxai_s3.env import LuxAIS3Env
from luxai_s3.params import env_params_ranges
from luxai_s3.state import gen_map
from luxai_s3.wrappers import LuxAIS3GymEnv, RecordEpisode

if __name__ == "__main__":
    import numpy as np
    jax.config.update('jax_numpy_dtype_promotion', 'strict')

    np.random.seed(2)

    # the first env params is not batched and is used to initialize any static / unchaging values
    # like map size, max units etc.
    # note auto_reset=False for speed reasons. If True, the default jax code will attempt to reset each time and discard the reset if its not time to reset
    # due to jax branching logic. It should be kept false and instead lax.scan followed by a reset after max episode steps should be used when possible since games
    # can't end early.
    env = LuxAIS3Env(auto_reset=False, fixed_env_params=EnvParams())
    num_envs = 100
    seed = 0
    rng_key = jax.random.key(seed)
    reset_fn = jax.vmap(env.reset)
    step_fn = jax.vmap(env.step)

    # sample random params initially
    def sample_params(rng_key):
        randomized_game_params = dict()
        for k, v in env_params_ranges.items():
            rng_key, subkey = jax.random.split(rng_key)
            if isinstance(v[0], int):
                randomized_game_params[k] = jax.random.choice(subkey, jax.numpy.array(v, dtype=jnp.int16))
            else:
                randomized_game_params[k] = jax.random.choice(subkey, jax.numpy.array(v, dtype=jnp.float32))
        params = EnvParams(**randomized_game_params)
        return params

    rng_key, subkey = jax.random.split(rng_key)
    env_params = jax.vmap(sample_params)(jax.random.split(subkey, num_envs))
    action_space = env.action_space() # note that this can generate sap actions beyond range atm
    sample_action = jax.vmap(action_space.sample)
    obs, state = reset_fn(jax.random.split(subkey, num_envs), env_params)
    obs, state, reward, terminated_dict, truncated_dict, info = step_fn(
        jax.random.split(subkey, num_envs), 
        state, 
        sample_action(jax.random.split(subkey, num_envs)), 
        env_params
    )

    max_episode_steps = env.fixed_env_params.max_steps_in_match * env.fixed_env_params.match_count_per_episode
    print("Benchmarking reset + for loop over jax.step time")
    stime = time.time()
    obs, state = reset_fn(jax.random.split(subkey, num_envs), env_params)
    for _ in range(max_episode_steps):
        obs, state, reward, terminated_dict, truncated_dict, info = step_fn(
            jax.random.split(subkey, num_envs), 
            state, 
            sample_action(jax.random.split(subkey, num_envs)), 
            env_params
        )    
    etime = time.time()
    print(f"FPS: {N * num_envs / (etime - stime):0.3f}. {N / (etime - stime):0.3f} parallel steps/s")
